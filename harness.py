#!/usr/bin/env python3
"""researcher-harness: the single high-level improvement loop.

One iteration is deliberately boring:

    reset target_repo/ to the best commit
      -> OpenCode proposes and edits code in target_repo/
        -> ./eval.sh target_repo scores it
          -> keep the change if it improved, otherwise revert

Everything the loop needs lives at the repo root:

    target_repo/      the code OpenCode improves (a working tree it can edit)
    knowledge_base/   papers, notes, directions the agent reads (read-only)
    eval.sh           the scorer; the agent writes it once if it is a stub
    opencode.jsonc    OpenCode configuration
    AGENTS.md         the agent's rules
    state/            cumulative memory (best.json, history.jsonl)   [runtime]
    runs/             per-iteration logs and diffs                   [runtime]

Usage:
    python3 harness.py run         # one iteration
    python3 harness.py loop [N]     # N iterations (default 10)
    python3 harness.py check        # verify the harness is ready
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
TARGET = ROOT / "target_repo"
KB = ROOT / "knowledge_base"
EVAL = ROOT / "eval.sh"
STATE = ROOT / "state"
RUNS = ROOT / "runs"
HISTORY = STATE / "history.jsonl"
BEST = STATE / "best.json"

# A lighter, cheaper model for the kb-researcher extraction subagent (same provider
# as the default main model, so it reuses NVIDIA_API_KEY). Override with KB_AGENT_MODEL.
FLASH_DEFAULT = "nvidia/deepseek-ai/deepseek-v4-flash"

# Knowledge-base context budgeting (all optional; safe defaults, zero setup required).
# A KB text file is inlined in full only if it is at most KB_INLINE_MAX_BYTES and the
# running total of inlined text stays at most KB_INLINE_TOTAL_BYTES. Everything else
# (large text, every PDF/binary, anything under knowledge_base/library/) goes to the
# manifest and is fetched on demand via the kb-researcher subagent.
KB_INLINE_MAX_BYTES_DEFAULT = 16_384
KB_INLINE_TOTAL_BYTES_DEFAULT = 65_536
KB_PREVIEW_CHARS = 200
KB_TEXT_SUFFIXES = {".md", ".txt", ".markdown", ".rst", ".csv", ".json", ".yaml", ".yml"}
KB_SKIP_NAMES = {"AGENTS.md", "README.md", ".gitignore", ".gitkeep"}


def load_dotenv() -> dict[str, str]:
    env = os.environ.copy()
    env_file = ROOT / ".env"
    if env_file.exists():
        for raw in env_file.read_text().splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            env.setdefault(k.strip(), v.strip().strip('"').strip("'"))
    env.setdefault("OPENCODE_CONFIG", str(ROOT / "opencode.jsonc"))
    return env


def run(cmd: list[str], *, cwd: Path = ROOT, env: dict[str, str] | None = None,
        check: bool = True, capture: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        cwd=str(cwd),
        env=env,
        text=True,
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.STDOUT if capture else None,
        check=check,
    )


def git(args: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    return run(["git", "-C", str(TARGET), *args], check=check)


def target_is_git_repo() -> bool:
    if not TARGET.exists():
        return False
    p = git(["rev-parse", "--is-inside-work-tree"], check=False)
    return p.returncode == 0 and "true" in (p.stdout or "")


def target_dirty() -> bool:
    p = git(["status", "--porcelain"], check=True)
    return bool((p.stdout or "").strip())


def ensure_target_repo() -> None:
    TARGET.mkdir(parents=True, exist_ok=True)

    if not target_is_git_repo():
        git(["init"])
        git(["config", "user.name", "researcher-harness"])
        git(["config", "user.email", "researcher-harness@example.invalid"])
        git(["config", "commit.gpgsign", "false"])
        placeholder = TARGET / ".gitkeep"
        placeholder.touch(exist_ok=True)
        git(["add", "-A"])
        git(["commit", "-m", "researcher-harness baseline"])
        return

    # Make local commits work even in fresh clones without global git identity.
    git(["config", "user.name", "researcher-harness"], check=False)
    git(["config", "user.email", "researcher-harness@example.invalid"], check=False)
    git(["config", "commit.gpgsign", "false"], check=False)

    # If this is the first harness run, capture the current tree as baseline.
    if not BEST.exists() and target_dirty():
        git(["add", "-A"])
        git(["commit", "-m", "researcher-harness initial target state"])


def parse_eval_json(stdout: str) -> dict[str, Any]:
    lines = [ln.strip() for ln in stdout.splitlines() if ln.strip()]
    if not lines:
        raise ValueError("eval produced no stdout")
    last = lines[-1]
    obj = json.loads(last)
    if "score" not in obj or "higher_is_better" not in obj:
        raise ValueError("eval JSON must contain score and higher_is_better")
    obj["score"] = float(obj["score"])
    if not (obj["score"] == obj["score"]) or obj["score"] in (float("inf"), float("-inf")):
        raise ValueError(f"eval score must be a finite number, got: {obj['score']}")
    obj["higher_is_better"] = bool(obj["higher_is_better"])
    obj.setdefault("summary", "")
    return obj


def run_eval(run_dir: Path) -> dict[str, Any]:
    if not EVAL.exists():
        raise FileNotFoundError(f"missing eval script: {EVAL}")
    EVAL.chmod(EVAL.stat().st_mode | 0o111)

    p = subprocess.run(
        [str(EVAL), str(TARGET)],
        cwd=str(ROOT),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    (run_dir / "eval.stdout.txt").write_text(p.stdout or "")
    (run_dir / "eval.stderr.txt").write_text(p.stderr or "")
    obj = parse_eval_json(p.stdout or "")
    obj["returncode"] = p.returncode
    return obj


def is_better(candidate: dict[str, Any], incumbent: dict[str, Any] | None) -> bool:
    if incumbent is None:
        return True
    if candidate["higher_is_better"] != incumbent["higher_is_better"]:
        raise ValueError("eval higher_is_better changed; refusing to compare")
    if candidate["higher_is_better"]:
        return candidate["score"] > incumbent["score"]
    return candidate["score"] < incumbent["score"]


def read_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    return json.loads(path.read_text())


def write_json(path: Path, obj: dict[str, Any]) -> None:
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n")


def append_history(obj: dict[str, Any]) -> None:
    with HISTORY.open("a") as f:
        f.write(json.dumps(obj, sort_keys=True) + "\n")


def collect_context_tail(max_lines: int = 20) -> str:
    if not HISTORY.exists():
        return ""
    lines = HISTORY.read_text().splitlines()
    return "\n".join(lines[-max_lines:])


def _env_int(env: dict[str, str], key: str, default: int) -> int:
    raw = env.get(key)
    if raw is None or not raw.strip():
        return default
    try:
        val = int(raw.strip())
    except ValueError:
        return default
    return val if val >= 0 else default


def _human_size(n: float) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.0f}{unit}" if unit == "B" else f"{n / 1024:.1f}{unit}"
        n /= 1024
    return f"{n:.0f}B"


def _classify_kb_files(env: dict[str, str]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Walk knowledge_base/ and split files into (inline, manifest_only).

    inline:        small text files whose full contents go into the prompt, subject to a
                   per-file cap and a cumulative total cap.
    manifest_only: large text files, ALL non-text files (PDFs/binaries), and anything
                   under knowledge_base/library/ — referenced in the manifest and fetched
                   on demand by the kb-researcher subagent.
    Each entry: {rel, kind, size, lines, preview, text}.
    """
    inline: list[dict[str, Any]] = []
    manifest_only: list[dict[str, Any]] = []
    if not KB.exists():
        return inline, manifest_only

    per_file_cap = _env_int(env, "KB_INLINE_MAX_BYTES", KB_INLINE_MAX_BYTES_DEFAULT)
    total_cap = _env_int(env, "KB_INLINE_TOTAL_BYTES", KB_INLINE_TOTAL_BYTES_DEFAULT)
    used = 0

    for p in sorted(KB.rglob("*")):
        if not p.is_file() or p.name in KB_SKIP_NAMES:
            continue
        rel_to_kb = p.relative_to(KB)
        in_library = rel_to_kb.parts[:1] == ("library",)
        try:
            size = p.stat().st_size
        except OSError:
            continue
        is_text = p.suffix.lower() in KB_TEXT_SUFFIXES
        entry: dict[str, Any] = {
            "rel": str(p.relative_to(ROOT)),
            "kind": "text" if is_text else f"binary ({p.suffix.lower() or 'no-ext'})",
            "size": size,
            "lines": None,
            "preview": "",
            "text": None,
        }

        if is_text:
            try:
                txt = p.read_text(errors="replace")
            except Exception:
                entry["preview"] = "(unreadable text)"
                manifest_only.append(entry)
                continue
            entry["lines"] = txt.count("\n") + (1 if txt and not txt.endswith("\n") else 0)
            entry["preview"] = next((ln.strip() for ln in txt.splitlines() if ln.strip()), "")[:KB_PREVIEW_CHARS]
            nbytes = len(txt.encode("utf-8", errors="replace"))
            if not in_library and nbytes <= per_file_cap and used + nbytes <= total_cap:
                entry["text"] = txt
                used += nbytes
                inline.append(entry)
            else:
                manifest_only.append(entry)
        else:
            # PDFs and other binaries are never inlined; kb-researcher extracts them.
            manifest_only.append(entry)

    return inline, manifest_only


def knowledge_manifest(env: dict[str, str] | None = None) -> str:
    """Render the knowledge-base section for the iteration prompt.

    Two parts: the full text of the small 'core' files, then a manifest listing EVERY
    file (path, type, size, lines, first-line preview). Large text and all PDFs/binaries
    appear only in the manifest and must be read via the kb-researcher subagent rather
    than dumped into context. The manifest lists inlined files too, so the agent always
    has a complete map of paths even if delegation never happens.
    """
    env = env if env is not None else load_dotenv()
    inline, manifest_only = _classify_kb_files(env)
    if not inline and not manifest_only:
        return ""

    parts: list[str] = []
    if inline:
        parts.append("Inlined knowledge base (small curated material, full text):")
        for e in inline:
            parts.append(f"\n--- {e['rel']} ({e['lines']} lines, {_human_size(e['size'])}) ---\n{e['text']}")

    parts.append("\nKnowledge base manifest (delegate large items to the kb-researcher subagent):")
    for e in sorted(inline + manifest_only, key=lambda e: e["rel"]):
        inlined = "inlined above" if e.get("text") is not None else "NOT inlined — extract on demand"
        loc = f"{e['lines']} lines" if e["lines"] is not None else "binary/pdf"
        preview = f" | first line: {e['preview']!r}" if e["preview"] else ""
        parts.append(f"- {e['rel']} [{e['kind']}, {_human_size(e['size'])}, {loc}; {inlined}]{preview}")

    return "\n".join(parts).strip()


def render_runtime_config(env: dict[str, str]) -> Path | None:
    """Render a runtime OpenCode config with the kb-researcher model resolved.

    The tracked opencode.jsonc ships a flash-tier default for the extraction subagent;
    KB_AGENT_MODEL (if set) overrides it. We can't pass a per-subagent model on the CLI,
    so we substitute it into a complete copy of the config and point OPENCODE_CONFIG at
    it. Best-effort: if anything goes wrong we fall back to the tracked config, whose
    static flash default still applies. Requires opencode.jsonc to keep // comments on
    their own lines (it does).
    """
    src = ROOT / "opencode.jsonc"
    if not src.exists():
        return None
    kb_model = (env.get("KB_AGENT_MODEL") or "").strip() or FLASH_DEFAULT
    try:
        body = "\n".join(ln for ln in src.read_text().splitlines() if not ln.lstrip().startswith("//"))
        cfg = json.loads(body)
        agents = cfg.get("agent")
        if not isinstance(agents, dict) or "kb-researcher" not in agents:
            return None  # nothing to override; use the tracked config as-is
        agents["kb-researcher"]["model"] = kb_model
        STATE.mkdir(exist_ok=True)
        out = STATE / "opencode.runtime.json"
        out.write_text(json.dumps(cfg, indent=2) + "\n")
        return out
    except Exception:
        return None


def invoke_opencode(prompt: str, run_dir: Path, title: str) -> int:
    env = load_dotenv()
    model = env.get("OPENCODE_MODEL", "nvidia/deepseek-ai/deepseek-v4-pro")

    runtime_cfg = render_runtime_config(env)
    if runtime_cfg is not None:
        env["OPENCODE_CONFIG"] = str(runtime_cfg)

    cmd = [
        "opencode",
        "run",
        "--dir", str(ROOT),
        "--model", model,
        "--format", "json",
        "--title", title,
    ]

    if env.get("OPENCODE_CONTINUE", "0") == "1":
        cmd.append("--continue")

    # The harness assumes a sandbox and headless, unattended operation, so it
    # skips interactive permission prompts by default — a run with no human in
    # the loop cannot answer them. Set OPENCODE_AUTO_APPROVE=0 only for manual,
    # supervised runs in a trusted environment.
    if env.get("OPENCODE_AUTO_APPROVE", "1") != "0":
        cmd.append("--dangerously-skip-permissions")

    cmd.append(prompt)

    (run_dir / "opencode.cmd.txt").write_text(" ".join(shlex.quote(x) for x in cmd) + "\n")
    p = run(cmd, env=env, check=False)
    (run_dir / "opencode.jsonl").write_text(p.stdout or "")
    return p.returncode


def make_eval_if_needed(run_dir: Path) -> None:
    if EVAL.exists() and "TODO_HARNESS_EVAL" not in EVAL.read_text(errors="replace"):
        return

    prompt = """
You are setting up the initial evaluator for researcher-harness.

Allowed edit:
- eval.sh only

Read:
- target_repo/
- knowledge_base/ (small notes are fine to read directly; for large files or PDFs, ask the
  kb-researcher subagent for the specific facts you need instead of reading the whole file)

Task:
Create the simplest meaningful eval script for this repo. It must be deterministic, runnable from the harness root, and obey this contract:

  ./eval.sh target_repo

The final stdout line must be JSON:
  {"score": <number>, "higher_is_better": <true|false>, "summary": "<short metric description>"}

Prefer an existing test/benchmark/smoke command from target_repo. If the real benchmark is expensive, create a cheap proxy eval and say so in the summary. Keep it boring.
"""
    code = invoke_opencode(prompt, run_dir, "researcher-harness create eval")
    if code != 0:
        raise RuntimeError("OpenCode failed while creating eval.sh")
    if not EVAL.exists():
        raise RuntimeError("OpenCode did not create eval.sh")
    EVAL.chmod(EVAL.stat().st_mode | 0o111)


def ensure_baseline(run_dir: Path) -> dict[str, Any]:
    best = read_json(BEST)
    if best is not None:
        return best

    eval_obj = run_eval(run_dir)
    commit = git(["rev-parse", "HEAD"]).stdout.strip()
    best = {
        "run_id": "baseline",
        "score": eval_obj["score"],
        "higher_is_better": eval_obj["higher_is_better"],
        "summary": eval_obj.get("summary", ""),
        "commit": commit,
        "created_at": dt.datetime.now(dt.UTC).isoformat(),
    }
    write_json(BEST, best)
    append_history({"event": "baseline", **best})
    return best


def save_diff(run_dir: Path) -> None:
    (run_dir / "git.status.txt").write_text(git(["status", "--short"], check=False).stdout or "")
    (run_dir / "git.diff.patch").write_text(git(["diff", "--binary"], check=False).stdout or "")
    (run_dir / "git.diff.stat.txt").write_text(git(["diff", "--stat"], check=False).stdout or "")


def reset_to_best(best: dict[str, Any]) -> None:
    commit = best.get("commit")
    if not commit:
        return
    git(["reset", "--hard", commit], check=False)
    git(["clean", "-fd"], check=False)


def run_iteration() -> None:
    STATE.mkdir(exist_ok=True)
    RUNS.mkdir(exist_ok=True)
    ensure_target_repo()

    # Microsecond precision keeps run_ids unique even when iterations are fast.
    run_id = dt.datetime.now(dt.UTC).strftime("%Y%m%dT%H%M%S_%fZ")
    run_dir = RUNS / run_id
    run_dir.mkdir(parents=True, exist_ok=False)

    make_eval_if_needed(run_dir)
    best = ensure_baseline(run_dir)
    reset_to_best(best)

    env = load_dotenv()
    prompt = f"""
You are running one autonomous research iteration in `researcher-harness`.

Goal:
Improve the target repository's eval score.

Canonical target repo:
- target_repo/

Read-only evidence:
- knowledge_base/
- state/history.jsonl
- state/best.json
- runs/

Evaluation command:
- ./eval.sh target_repo

Best known result:
{json.dumps(best, indent=2)}

Recent history:
{collect_context_tail() or "(none)"}

Knowledge base:
{knowledge_manifest(env) or "(no knowledge base material yet; inspect knowledge_base/ directly if it appears later)"}

Using the knowledge base:
- The "Inlined" material above is the full text of the small curated notes — use it directly.
- For any manifest item marked "NOT inlined" (large notes, papers, PDFs, datasets), DO NOT read
  the whole file into your own context. Delegate to the kb-researcher subagent with a SPECIFIC
  question, e.g. "@kb-researcher In knowledge_base/paper.pdf, what hyperparameters and ablation
  results does Section 4 report for the method we're improving?" It reads in an isolated context
  and returns only the distilled findings with citations. Ask follow-ups as your plan narrows.
- If the kb-researcher subagent is unavailable, fall back to reading the specific manifest paths
  yourself, but only the parts you need (grep/section, or `pdftotext <file> -` for PDFs) — never
  paste whole documents.

Rules:
1. Edit only files under target_repo/.
2. Make one small coherent change.
3. Use the knowledge base (inlined notes + kb-researcher findings) and past outcomes to choose the change.
4. Run ./eval.sh target_repo before finishing if feasible.
5. Do not edit harness.py, eval.sh, opencode.jsonc, AGENTS.md, state/, runs/, knowledge_base/, or the harness directories (setup/, orchestrator/, messaging/).
6. Prefer simple, reviewable diffs over large rewrites.

Return a concise explanation of what changed and why.
"""
    opencode_rc = invoke_opencode(prompt, run_dir, f"researcher-harness iteration {run_id}")

    save_diff(run_dir)

    try:
        eval_obj = run_eval(run_dir)
        eval_error = None
    except Exception as e:
        eval_obj = {
            "score": best["score"],
            "higher_is_better": best["higher_is_better"],
            "summary": f"eval failed: {e}",
        }
        eval_error = repr(e)

    improved = False
    commit = best.get("commit")
    if opencode_rc == 0 and eval_error is None and target_dirty() and is_better(eval_obj, best):
        git(["add", "-A"])
        git(["commit", "-m", f"researcher-harness {run_id}: score {eval_obj['score']}"])
        commit = git(["rev-parse", "HEAD"]).stdout.strip()
        improved = True
        new_best = {
            "run_id": run_id,
            "score": eval_obj["score"],
            "higher_is_better": eval_obj["higher_is_better"],
            "summary": eval_obj.get("summary", ""),
            "commit": commit,
            "created_at": dt.datetime.now(dt.UTC).isoformat(),
        }
        write_json(BEST, new_best)
    else:
        reset_to_best(best)

    record = {
        "event": "iteration",
        "run_id": run_id,
        "opencode_returncode": opencode_rc,
        "score": eval_obj["score"],
        "higher_is_better": eval_obj["higher_is_better"],
        "summary": eval_obj.get("summary", ""),
        "improved": improved,
        "commit": commit,
        "eval_error": eval_error,
    }
    write_json(run_dir / "result.json", record)
    append_history(record)
    print(json.dumps(record, indent=2, sort_keys=True))


def run_loop(n: int) -> None:
    completed = 0
    for i in range(1, n + 1):
        print(f"=== researcher-harness iteration {i}/{n} ===", file=sys.stderr)
        try:
            run_iteration()
        except Exception as e:
            print(f"researcher-harness: iteration {i} failed ({e}); "
                  f"stopping after {completed} completed.", file=sys.stderr)
            raise SystemExit(1)
        completed += 1
    print(f"researcher-harness: completed {completed}/{n} iterations.", file=sys.stderr)


def check() -> None:
    for p in [KB, TARGET, STATE, RUNS]:
        p.mkdir(parents=True, exist_ok=True)

    for tool in ("python3", "git"):
        if shutil.which(tool) is None:
            raise SystemExit(f"{tool} is required but not found in PATH")

    if shutil.which("opencode") is None:
        print("WARNING: opencode is not installed. Install it with setup/setup_opencode.sh "
              "(curl -fsSL https://opencode.ai/install | bash).", file=sys.stderr)

    if not EVAL.exists():
        raise SystemExit("missing eval.sh")
    if "TODO_HARNESS_EVAL" in EVAL.read_text(errors="replace"):
        print("WARNING: eval.sh is still the placeholder; replace it or let the first run "
              "auto-generate one from knowledge_base/ and target_repo/.", file=sys.stderr)

    if load_dotenv().get("OPENCODE_AUTO_APPROVE", "1") == "0":
        print("WARNING: OPENCODE_AUTO_APPROVE=0 disables --dangerously-skip-permissions; "
              "headless runs will stall on permission prompts. The harness assumes a "
              "sandbox and unattended operation — leave it unset or 1 unless you are "
              "supervising the run.", file=sys.stderr)

    print(f"root:        {ROOT}")
    print(f"target repo: {TARGET}")
    print(f"knowledge:   {KB}")
    print(f"eval:        {EVAL}")
    print("Setup check complete.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="researcher-harness: autonomous improvement loop over target_repo/")
    sub = parser.add_subparsers(dest="cmd")
    sub.add_parser("run", help="run a single improvement iteration")
    lp = sub.add_parser("loop", help="run N improvement iterations (default 10)")
    lp.add_argument("n", nargs="?", type=int, default=10)
    sub.add_parser("check", help="verify the harness is ready to run")
    args = parser.parse_args()

    cmd = args.cmd or "run"
    if cmd == "check":
        check()
    elif cmd == "loop":
        run_loop(args.n)
    else:
        run_iteration()


if __name__ == "__main__":
    main()
