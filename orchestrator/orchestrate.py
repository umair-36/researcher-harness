#!/usr/bin/env python3
"""Very lightweight orchestrator for researcher-harness.

It sits one level above the operational research loop:

    messaging  ->  decide  ->  operational/scripts (run_once / loop)  ->  messaging

That is: read a user request from the messaging layer, decide what to do,
drive the harness, and report back. It is deliberately tiny and stdlib-only.

The decision backend is pluggable and has NO hard default (ORCH_BACKEND):

    none      rule-based keyword routing, no model, works offline
    nemotron  NVIDIA NIM chat model (ORCH_MODEL + NVIDIA_API_KEY)
    openclaw  external command (ORCH_CMD): message on stdin -> action JSON on stdout
    custom    external command (ORCH_CMD): same contract as openclaw

An "action" is JSON: {"action": "run"|"status"|"stop", "iterations": <int>, "reason": "..."}.

Commands:
    orchestrator/run.sh status      summarize best.json + recent history, send it
    orchestrator/run.sh run [N]     run N harness iterations, then send status
    orchestrator/run.sh serve       poll messaging for requests and act until told to stop
    orchestrator/run.sh decide MSG  (debug) print the action a message would map to
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
OPERATIONAL = REPO_ROOT / "operational"
SCRIPTS = OPERATIONAL / "scripts"
STATE = OPERATIONAL / "state"
BEST = STATE / "best.json"
HISTORY = STATE / "history.jsonl"

# Reuse the messaging client (load_env, send, poll, _http) without packaging.
sys.path.insert(0, str(REPO_ROOT / "messaging"))
import client as messaging  # noqa: E402

env = messaging.load_env()

NIM_URL = "https://integrate.api.nvidia.com/v1/chat/completions"


# ── driving the operational loop ──────────────────────────────────────────────

def run_iterations(n: int) -> tuple[int, str]:
    loop = SCRIPTS / "loop.sh"
    if not loop.exists():
        return 1, f"missing {loop.relative_to(REPO_ROOT)}"
    p = subprocess.run(["bash", str(loop), str(n)], cwd=str(OPERATIONAL),
                       text=True, capture_output=True)
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def status_summary(max_history: int = 5) -> str:
    lines: list[str] = []
    if BEST.exists():
        try:
            best = json.loads(BEST.read_text())
            direction = "higher" if best.get("higher_is_better") else "lower"
            lines.append(f"best score: {best.get('score')} ({direction} is better)"
                         f" - {best.get('summary', '')}".rstrip())
            lines.append(f"best commit: {str(best.get('commit', '?'))[:12]}"
                         f" (run {best.get('run_id', '?')})")
        except Exception as e:
            lines.append(f"best.json unreadable: {e}")
    else:
        lines.append("no baseline yet (run an iteration first)")

    if HISTORY.exists():
        recent = [ln for ln in HISTORY.read_text().splitlines() if ln.strip()][-max_history:]
        if recent:
            lines.append(f"recent ({len(recent)}):")
            for ln in recent:
                try:
                    e = json.loads(ln)
                except Exception:
                    continue
                tag = "improved" if e.get("improved") else e.get("event", "")
                lines.append(f"  {e.get('run_id', '?')}: score={e.get('score')} {tag}".rstrip())
    return "\n".join(lines) if lines else "no state yet"


# ── decision backends ─────────────────────────────────────────────────────────

def _extract_action(text: str) -> dict | None:
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        return None
    try:
        obj = json.loads(m.group(0))
    except Exception:
        return None
    return obj if obj.get("action") in ("run", "status", "stop") else None


def _rule_decide(msg: str) -> dict:
    m = msg.strip().lower()
    if any(w in m for w in ("stop", "quit", "halt", "exit", "pause")):
        return {"action": "stop", "reason": "stop keyword"}
    if any(w in m for w in ("status", "progress", "score", "report", "how")):
        return {"action": "status", "reason": "status keyword"}
    if any(w in m for w in ("run", "iterate", "loop", "go", "start", "improve")):
        num = re.search(r"(\d+)", m)
        n = int(num.group(1)) if num else int(env.get("ORCH_ITERATIONS", "1") or 1)
        return {"action": "run", "iterations": n, "reason": "run keyword"}
    return {"action": "status", "reason": "no match -> status"}


def _nim_decide(msg: str) -> dict | None:
    model = (env.get("ORCH_MODEL") or "").strip()
    key = (env.get("NVIDIA_API_KEY") or "").strip()
    if not model or not key or key.endswith("REPLACE_ME"):
        return None
    system = (
        "You route messages for a research-loop orchestrator. Reply with ONLY a compact "
        'JSON object: {"action": "run"|"status"|"stop", "iterations": <int for run>, '
        '"reason": "<short>"}. Use run to start research iterations, status to report '
        "progress, stop to halt. No prose."
    )
    payload = json.dumps({
        "model": model,
        "messages": [{"role": "system", "content": system},
                     {"role": "user", "content": msg}],
        "temperature": 0,
        "max_tokens": 120,
    }).encode()
    status, body = messaging._http(
        "POST", NIM_URL, data=payload,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"})
    if not 200 <= status < 300:
        return None
    try:
        content = json.loads(body)["choices"][0]["message"]["content"]
    except Exception:
        return None
    return _extract_action(content)


def _cmd_decide(msg: str) -> dict | None:
    cmd = (env.get("ORCH_CMD") or "").strip()
    if not cmd:
        return None
    try:
        p = subprocess.run(cmd, shell=True, input=msg, text=True,
                           capture_output=True, timeout=120)
    except Exception:
        return None
    return _extract_action(p.stdout or "") if p.returncode == 0 else None


def decide(msg: str) -> dict:
    b = (env.get("ORCH_BACKEND") or "none").strip().lower()
    action = None
    if b == "nemotron":
        action = _nim_decide(msg)
    elif b in ("openclaw", "custom"):
        action = _cmd_decide(msg)
    return action or _rule_decide(msg)  # rules drive 'none' and back up every backend


# ── execution ─────────────────────────────────────────────────────────────────

def execute(action: dict) -> tuple[str, bool]:
    """Return (reply_text, should_stop)."""
    a = action.get("action", "status")
    if a == "stop":
        return "orchestrator stopping (requested).", True
    if a == "run":
        n = int(action.get("iterations") or env.get("ORCH_ITERATIONS", "1") or 1)
        n = max(1, min(n, 100))
        rc, _ = run_iterations(n)
        return f"ran {n} iteration(s) (exit {rc}).\n" + status_summary(), False
    return status_summary(), False


def serve() -> int:
    interval = int(env.get("ORCH_POLL_SECONDS", "10") or 10)
    messaging.send(
        f"orchestrator online (backend={env.get('ORCH_BACKEND', 'none')}, "
        f"messaging={messaging.backend(env)}). Send 'run N', 'status', or 'stop'.",
        title="harness orchestrator", env=env)
    print(f"orchestrator serving; polling every {interval}s. Ctrl-C to stop.")
    while True:
        try:
            msgs = messaging.poll(env)
        except Exception as e:
            print(f"poll error: {e}", file=sys.stderr)
            msgs = []
        for m in msgs:
            text = m.get("text", "")
            print(f"< {text!r}")
            action = decide(text)
            reply, stop = execute(action)
            messaging.send(f"[{action.get('action')}] {action.get('reason', '')}\n{reply}",
                           title="harness orchestrator", env=env)
            print(f"> {action}")
            if stop:
                return 0
        time.sleep(interval)


def main() -> int:
    ap = argparse.ArgumentParser(description="researcher-harness lightweight orchestrator")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status", help="report best score + recent history")
    r = sub.add_parser("run", help="run N harness iterations")
    r.add_argument("n", nargs="?", type=int, default=None)
    sub.add_parser("serve", help="poll messaging and act until told to stop")
    d = sub.add_parser("decide", help="(debug) show the action a message maps to")
    d.add_argument("message")
    args = ap.parse_args()

    if args.cmd == "status":
        s = status_summary()
        print(s)
        messaging.send(s, title="harness status", env=env)
        return 0
    if args.cmd == "run":
        n = args.n if args.n is not None else int(env.get("ORCH_ITERATIONS", "1") or 1)
        reply, _ = execute({"action": "run", "iterations": n})
        print(reply)
        messaging.send(reply, title="harness run", env=env)
        return 0
    if args.cmd == "serve":
        return serve()
    if args.cmd == "decide":
        print(json.dumps(decide(args.message)))
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
