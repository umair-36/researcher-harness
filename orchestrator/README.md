# orchestrator/

A very lightweight layer above the operational research loop. It reads a user
request from the messaging channel, decides what to do, drives the harness, and
reports the result back:

```text
messaging  ->  decide  ->  operational/scripts (run_once / loop)  ->  messaging
```

It is intentionally tiny and stdlib-only (`orchestrate.py`, ~200 lines). Drive
it through `run.sh`:

```bash
orchestrator/run.sh status            # report best score + recent history
orchestrator/run.sh run 5             # run 5 iterations, then report status
orchestrator/run.sh serve             # poll messaging and act until told to stop
orchestrator/run.sh decide "run 3"    # debug: print the action a message maps to
```

## Decision backends (pluggable, no hard default)

Set `ORCH_BACKEND` in `operational/.env` (via `setup/setup_orchestrator.sh`):

| `ORCH_BACKEND` | How a message becomes an action |
|----------------|---------------------------------|
| `none` | Rule-based keyword routing (`run N`, `status`, `stop`, …). No model, works offline. |
| `nemotron` | Sends the message to an NVIDIA NIM chat model (`ORCH_MODEL`, `NVIDIA_API_KEY`) and parses the JSON it returns. |
| `openclaw` | Runs `ORCH_CMD` with the message on stdin; reads an action JSON from stdout. |
| `custom` | Same contract as `openclaw`, for any orchestrator you prefer. |

Every backend falls back to the rule-based router if the model/command is
unavailable or returns nothing parseable, so the orchestrator always does
something sensible.

## Action contract

`decide()` returns, and external backends must emit, a JSON object:

```json
{"action": "run", "iterations": 5, "reason": "user asked to run"}
{"action": "status", "reason": "user asked for progress"}
{"action": "stop", "reason": "user asked to stop"}
```

`iterations` is clamped to `1..100`; when omitted it falls back to
`ORCH_ITERATIONS`.

## serve mode

`serve` polls the messaging inbox every `ORCH_POLL_SECONDS`, handles each
inbound message, and replies through the same channel. It exits cleanly on a
`stop` action. With the default `localfile` messaging backend you can queue work
with:

```bash
echo "run 3" > messaging/inbox/req.txt
```
