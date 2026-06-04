#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "target" / "repo"
EVAL = ROOT / "eval" / "run_eval.sh"
STATE = ROOT / "state"
RUNS = ROOT / "runs"
HISTORY = STATE / "history.jsonl"
BEST = STATE / "best.json"


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
        git(["config", "user.name", "research-harness"])
        git(["config", "user.email", "research-harness@example.invalid"])
        git(["config", "commit.gpgsign", "false"])
        placeholder = TARGET / ".gitkeep"
        placeholder.touch(exist_ok=True)
        git(["add", "-A"])
        git(["commit", "-m", "research-harness baseline"])
        return

    # Make local commits work even in fresh clones without global git identity.
    git(["config", "user.name", "research-harness"], check=False)
    git(["config", "user.email", "research-harness@example.invalid"], check=False)
    git(["config", "commit.gpgsign", "false"], check=False)

    # If this is the first harness run, capture the current tree as baseline.
    if not BEST.exists() and target_dirty():
        git(["add", "-A"])
        git(["commit", "-m", "research-harness initial target state"])


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


def direction_index() -> str:
    parts: list[str] = []
    for base in [ROOT / "paper", ROOT / "directions"]:
        if not base.exists():
            continue
        for p in sorted(base.rglob("*")):
            if p.is_file():
                rel = p.relative_to(ROOT)
                if p.suffix.lower() in {".md", ".txt"}:
                    try:
                        txt = p.read_text(errors="replace")
                        truncated = txt[:4000]
                        suffix = "\n[...truncated]" if len(txt) > 4000 else ""
                        parts.append(f"\n--- {rel} ---\n{truncated}{suffix}")
                    except Exception:
                        parts.append(f"\n--- {rel} ---\n(unreadable text)")
                else:
                    parts.append(f"\n--- {rel} ---\n(non-text file present)")
    return "\n".join(parts).strip()


def invoke_opencode(prompt: str, run_dir: Path, title: str) -> int:
    env = load_dotenv()
    model = env.get("OPENCODE_MODEL", "nvidia/deepseek-ai/deepseek-v4-pro")

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

    if env.get("OPENCODE_AUTO_APPROVE", "0") == "1":
        cmd.append("--dangerously-skip-permissions")

    cmd.append(prompt)

    (run_dir / "opencode.cmd.txt").write_text(" ".join(shlex.quote(x) for x in cmd) + "\n")
    p = run(cmd, env=env, check=False)
    (run_dir / "opencode.jsonl").write_text(p.stdout or "")
    return p.returncode


def make_eval_if_needed(run_dir: Path) -> None:
    if EVAL.exists() and "TODO_HARNESS_EVAL" not in EVAL.read_text(errors="replace"):
        return

    prompt = f"""
You are setting up the initial evaluator for research-harness.

Allowed edit:
- eval/run_eval.sh only

Read:
- target/repo/
- paper/
- directions/

Task:
Create the simplest meaningful eval script for this paper/repo. It must be deterministic, runnable from the harness root, and obey this contract:

  ./eval/run_eval.sh target/repo

The final stdout line must be JSON:
  {{"score": <number>, "higher_is_better": <true|false>, "summary": "<short metric description>"}}

Prefer an existing test/benchmark/smoke command from target/repo. If the paper's real benchmark is expensive, create a cheap proxy eval and say so in the summary. Keep it boring.
"""
    code = invoke_opencode(prompt, run_dir, "research-harness create eval")
    if code != 0:
        raise RuntimeError("OpenCode failed while creating eval/run_eval.sh")
    if not EVAL.exists():
        raise RuntimeError("OpenCode did not create eval/run_eval.sh")
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

    run_id = dt.datetime.now(dt.UTC).strftime("%Y%m%dT%H%M%SZ")
    run_dir = RUNS / run_id
    run_dir.mkdir(parents=True, exist_ok=False)

    make_eval_if_needed(run_dir)
    best = ensure_baseline(run_dir)
    reset_to_best(best)

    prompt = f"""
You are running one autonomous research iteration in `research-harness`.

Goal:
Improve the target repository's eval score.

Canonical target repo:
- target/repo/

Read-only evidence:
- paper/
- directions/
- state/history.jsonl
- state/best.json
- runs/

Evaluation command:
- ./eval/run_eval.sh target/repo

Best known result:
{json.dumps(best, indent=2)}

Recent history:
{collect_context_tail() or "(none)"}

Paper/direction notes index:
{direction_index() or "(no text notes; inspect files directly if useful)"}

Rules:
1. Edit only files under target/repo/.
2. Make one small coherent change.
3. Use the paper and past outcomes to choose the change.
4. Run ./eval/run_eval.sh target/repo before finishing if feasible.
5. Do not edit scripts/, eval/, state/, runs/, paper/, or directions/.
6. Prefer simple, reviewable diffs over large rewrites.

Return a concise explanation of what changed and why.
"""
    opencode_rc = invoke_opencode(prompt, run_dir, f"research-harness iteration {run_id}")

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
        git(["commit", "-m", f"research-harness {run_id}: score {eval_obj['score']}"])
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


def check() -> None:
    for p in [ROOT / "paper", ROOT / "directions", ROOT / "target", ROOT / "eval", ROOT / "scripts", STATE, RUNS]:
        p.mkdir(exist_ok=True)
    if not EVAL.exists():
        raise SystemExit("missing eval/run_eval.sh")
    if "TODO_HARNESS_EVAL" in EVAL.read_text(errors="replace"):
        print("WARNING: eval/run_eval.sh is still the placeholder; replace it or let the first run auto-generate one.", file=sys.stderr)
    print(f"root: {ROOT}")
    print(f"target repo: {TARGET}")
    print(f"eval: {EVAL}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", nargs="?", default="run", choices=["run"])
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    if args.check:
        check()
        return

    if args.command == "run":
        run_iteration()


if __name__ == "__main__":
    main()
