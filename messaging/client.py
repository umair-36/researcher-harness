#!/usr/bin/env python3
"""Unified, dependency-free messaging client for researcher-harness.

One small interface over several pluggable backends. The orchestrator uses it
to receive user requests and report results; you can also use it standalone.

Backends (selected by MESSAGING_BACKEND in operational/.env):

    localfile   inbox/outbox files under messaging/ (default; no external egress)
    ntfy        ntfy.sh topic           (simple push; optional inbound polling)
    telegram    Telegram bot            (sendMessage / getUpdates)
    discord     Discord incoming webhook (send-only)

Only stdlib is used, so it runs anywhere python3 does.

CLI:
    python3 messaging/client.py send "text" [--title T]
    python3 messaging/client.py poll
    python3 messaging/client.py backend
    python3 messaging/client.py test
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = REPO_ROOT / "operational" / ".env"
MSG_DIR = REPO_ROOT / "messaging"
INBOX = MSG_DIR / "inbox"
OUTBOX = MSG_DIR / "outbox"
STATE_FILE = MSG_DIR / ".state.json"


def load_env() -> dict[str, str]:
    """os.environ overlaid with operational/.env (environment wins)."""
    env = dict(os.environ)
    if ENV_FILE.exists():
        for raw in ENV_FILE.read_text().splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            env.setdefault(k.strip(), v.strip().strip('"').strip("'"))
    return env


def backend(env: dict[str, str] | None = None) -> str:
    env = env or load_env()
    return (env.get("MESSAGING_BACKEND") or "localfile").strip().lower()


def _state() -> dict[str, Any]:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except Exception:
            return {}
    return {}


def _save_state(st: dict[str, Any]) -> None:
    STATE_FILE.write_text(json.dumps(st, indent=2, sort_keys=True) + "\n")


def _http(method: str, url: str, *, data: bytes | None = None,
          headers: dict[str, str] | None = None, timeout: int = 20) -> tuple[int, str]:
    """Minimal HTTP. Returns (status, body); status 0 means the request never landed."""
    req = urllib.request.Request(url, data=data, method=method, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")
    except Exception as e:  # network disabled / DNS / timeout
        return 0, repr(e)


# ── send ────────────────────────────────────────────────────────────────────

def send(text: str, *, title: str | None = None, env: dict[str, str] | None = None) -> bool:
    env = env or load_env()
    b = backend(env)
    handler = {
        "localfile": lambda: _send_localfile(text, title),
        "ntfy": lambda: _send_ntfy(text, title, env),
        "telegram": lambda: _send_telegram(text, env),
        "discord": lambda: _send_discord(text, env),
    }.get(b)
    if handler is None:
        print(f"messaging: unknown MESSAGING_BACKEND={b!r}", file=sys.stderr)
        return False
    return handler()


def _send_localfile(text: str, title: str | None) -> bool:
    OUTBOX.mkdir(parents=True, exist_ok=True)
    ts = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%S_%f")
    path = OUTBOX / f"{ts}.txt"
    header = f"# {title}\n" if title else ""
    path.write_text(header + text.rstrip() + "\n")
    print(f"messaging[localfile]: wrote {path.relative_to(REPO_ROOT)}")
    return True


def _send_ntfy(text: str, title: str | None, env: dict[str, str]) -> bool:
    topic = (env.get("NTFY_TOPIC") or "").strip()
    server = (env.get("NTFY_SERVER") or "https://ntfy.sh").rstrip("/")
    if not topic:
        print("messaging[ntfy]: NTFY_TOPIC not set", file=sys.stderr)
        return False
    headers = {"Title": title} if title else {}
    status, body = _http("POST", f"{server}/{topic}", data=text.encode(), headers=headers)
    if not 200 <= status < 300:
        print(f"messaging[ntfy]: send failed ({status}): {body[:200]}", file=sys.stderr)
        return False
    return True


def _send_telegram(text: str, env: dict[str, str]) -> bool:
    token = (env.get("TELEGRAM_BOT_TOKEN") or "").strip()
    chat = (env.get("TELEGRAM_CHAT_ID") or "").strip()
    if not token or not chat:
        print("messaging[telegram]: TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID not set", file=sys.stderr)
        return False
    payload = json.dumps({"chat_id": chat, "text": text}).encode()
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    status, body = _http("POST", url, data=payload, headers={"Content-Type": "application/json"})
    if not 200 <= status < 300:
        print(f"messaging[telegram]: send failed ({status}): {body[:200]}", file=sys.stderr)
        return False
    return True


def _send_discord(text: str, env: dict[str, str]) -> bool:
    url = (env.get("DISCORD_WEBHOOK_URL") or "").strip()
    if not url:
        print("messaging[discord]: DISCORD_WEBHOOK_URL not set", file=sys.stderr)
        return False
    payload = json.dumps({"content": text[:1900]}).encode()
    status, body = _http("POST", url, data=payload, headers={"Content-Type": "application/json"})
    if not 200 <= status < 300:
        print(f"messaging[discord]: send failed ({status}): {body[:200]}", file=sys.stderr)
        return False
    return True


# ── poll (inbound) ────────────────────────────────────────────────────────────

def poll(env: dict[str, str] | None = None) -> list[dict[str, str]]:
    """Return new inbound messages as [{'id':..., 'text':...}]. Consumes them."""
    env = env or load_env()
    b = backend(env)
    if b == "localfile":
        return _poll_localfile()
    if b == "ntfy":
        return _poll_ntfy(env)
    if b == "telegram":
        return _poll_telegram(env)
    return []  # discord webhooks are send-only


def _poll_localfile() -> list[dict[str, str]]:
    INBOX.mkdir(parents=True, exist_ok=True)
    msgs: list[dict[str, str]] = []
    for p in sorted(INBOX.glob("*.txt")):
        msgs.append({"id": p.name, "text": p.read_text(errors="replace").strip()})
        p.rename(p.with_suffix(p.suffix + ".read"))  # mark consumed
    return msgs


def _poll_ntfy(env: dict[str, str]) -> list[dict[str, str]]:
    topic = (env.get("NTFY_TOPIC") or "").strip()
    server = (env.get("NTFY_SERVER") or "https://ntfy.sh").rstrip("/")
    if not topic:
        return []
    st = _state()
    since = st.get("ntfy_since", "all")
    status, body = _http("GET", f"{server}/{topic}/json?poll=1&since={since}")
    if not 200 <= status < 300:
        return []
    msgs: list[dict[str, str]] = []
    last_time = None
    for line in body.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except Exception:
            continue
        if isinstance(obj.get("time"), int):
            last_time = obj["time"]
        if obj.get("event") == "message" and obj.get("message"):
            msgs.append({"id": str(obj.get("id", "")), "text": obj["message"]})
    if last_time is not None:
        st["ntfy_since"] = last_time + 1
        _save_state(st)
    return msgs


def _poll_telegram(env: dict[str, str]) -> list[dict[str, str]]:
    token = (env.get("TELEGRAM_BOT_TOKEN") or "").strip()
    if not token:
        return []
    st = _state()
    offset = int(st.get("telegram_offset", 0) or 0)
    status, body = _http("GET", f"https://api.telegram.org/bot{token}/getUpdates?timeout=0&offset={offset}")
    if not 200 <= status < 300:
        return []
    try:
        data = json.loads(body)
    except Exception:
        return []
    msgs: list[dict[str, str]] = []
    max_update = offset
    for upd in data.get("result", []):
        uid = int(upd.get("update_id", 0))
        max_update = max(max_update, uid + 1)
        msg = upd.get("message") or upd.get("channel_post") or {}
        if msg.get("text"):
            msgs.append({"id": str(uid), "text": msg["text"]})
    if max_update != offset:
        st["telegram_offset"] = max_update
        _save_state(st)
    return msgs


# ── CLI ───────────────────────────────────────────────────────────────────────

def main() -> int:
    ap = argparse.ArgumentParser(description="researcher-harness messaging client")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("send", help="send a message")
    s.add_argument("text")
    s.add_argument("--title", default=None)
    sub.add_parser("poll", help="fetch + consume inbound messages")
    sub.add_parser("backend", help="print the active backend")
    sub.add_parser("test", help="send a test message")
    args = ap.parse_args()

    env = load_env()
    if args.cmd == "send":
        return 0 if send(args.text, title=args.title, env=env) else 1
    if args.cmd == "poll":
        for m in poll(env):
            print(json.dumps(m, ensure_ascii=False))
        return 0
    if args.cmd == "backend":
        print(backend(env))
        return 0
    if args.cmd == "test":
        ok = send("researcher-harness messaging test", title="harness test", env=env)
        print(f"{'ok' if ok else 'failed'} (backend: {backend(env)})")
        return 0 if ok else 1
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
