#!/usr/bin/env bash
# Smoke-tests researcher-harness end-to-end using the toy-classifier example.
# Does NOT require OpenCode or any API key.
# Uses a local mock agent that makes deterministic changes to target/repo.

set -uo pipefail

PASS=0; FAIL=0; declare -a ERRORS=()

ok()   { printf '  \033[32mPASS\033[0m  %s\n' "$*"; ((PASS++)) || true; }
fail() { printf '  \033[31mFAIL\033[0m  %s\n' "$*"; ((FAIL++)) || true; ERRORS+=("$*"); }
info() { printf '\n  ----  %s\n' "$*"; }

HARNESS_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
EXAMPLE="$HARNESS_ROOT/examples/toy-classifier"

# ── Preflight ──────────────────────────────────────────────────────────────

info "Preflight"

for dep in python3 git sed; do
    command -v "$dep" &>/dev/null \
        && ok "$dep in PATH" \
        || { fail "$dep not found"; exit 1; }
done

python3 -c "import sklearn" 2>/dev/null \
    && ok "scikit-learn available" \
    || { fail "scikit-learn not installed  (pip install scikit-learn)"; exit 1; }

[[ -d "$EXAMPLE" ]] \
    && ok "examples/toy-classifier found" \
    || { fail "example directory missing: $EXAMPLE"; exit 1; }

# ── Isolated workspace ─────────────────────────────────────────────────────

WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT

cp -r "$HARNESS_ROOT/scripts" "$WORK/"
for f in opencode.jsonc AGENTS.md; do
    [[ -f "$HARNESS_ROOT/$f" ]] && cp "$HARNESS_ROOT/$f" "$WORK/"
done
cp -r "$EXAMPLE/target"     "$WORK/"
cp -r "$EXAMPLE/eval"       "$WORK/"
cp -r "$EXAMPLE/paper"      "$WORK/"
cp -r "$EXAMPLE/directions" "$WORK/"
mkdir -p "$WORK/state" "$WORK/runs"

HARNESS_PY="$WORK/scripts/harness.py"
TRAIN_PY="$WORK/target/repo/train.py"
MOCK_BIN="$WORK/bin"
mkdir -p "$MOCK_BIN"

_run_harness() {
    PATH="$MOCK_BIN:$PATH" python3 "$HARNESS_PY" run >/dev/null 2>&1
    return $?
}

# ── Test 1: eval/run_eval.sh contract ──────────────────────────────────────

info "Test 1: eval/run_eval.sh contract"

EVAL_OUT=$("$WORK/eval/run_eval.sh" "$WORK/target/repo" 2>/dev/null || true)
EVAL_LAST=$(printf '%s' "$EVAL_OUT" | tail -1)
BASELINE_SCORE=$(printf '%s' "$EVAL_LAST" | python3 -c "
import json, sys
obj = json.loads(sys.stdin.read().strip())
assert 'score' in obj and 'higher_is_better' in obj, 'missing fields'
assert isinstance(obj['score'], (int, float)), 'score not numeric'
print(obj['score'])
" 2>/dev/null || true)

if [[ -n "${BASELINE_SCORE:-}" ]]; then
    ok "eval/run_eval.sh outputs valid JSON  (score=$BASELINE_SCORE)"
else
    fail "eval/run_eval.sh did not produce valid JSON: $EVAL_LAST"
    BASELINE_SCORE="0"
fi

# ── Test 2: baseline establishment ─────────────────────────────────────────

info "Test 2: baseline establishment (no-op mock agent)"

cat > "$MOCK_BIN/opencode" << 'EOF'
#!/usr/bin/env bash
# no-op: exit 0 without touching target/repo
exit 0
EOF
chmod +x "$MOCK_BIN/opencode"

_run_harness \
    && ok "harness.py run completed" \
    || fail "harness.py exited non-zero on first run"

[[ -f "$WORK/state/best.json" ]] \
    && ok "state/best.json created" \
    || fail "state/best.json missing after first run"

[[ -f "$WORK/state/history.jsonl" ]] \
    && ok "state/history.jsonl created" \
    || fail "state/history.jsonl missing after first run"

HAS_BASELINE=$(python3 -c "
import json, sys
events = [json.loads(l) for l in open(sys.argv[1]) if l.strip()]
print('yes' if any(e.get('event') == 'baseline' for e in events) else 'no')
" "$WORK/state/history.jsonl" 2>/dev/null || echo "error")
[[ "$HAS_BASELINE" == "yes" ]] \
    && ok "baseline event recorded in history.jsonl" \
    || fail "no baseline event found in history.jsonl"

# ── Test 3: improvement detected and committed ─────────────────────────────

info "Test 3: improvement (DecisionTree → RandomForest)"

cat > "$MOCK_BIN/opencode" << 'EOF'
#!/usr/bin/env bash
HARNESS_DIR=""
while [[ $# -gt 0 ]]; do
    case "$1" in --dir) HARNESS_DIR="$2"; shift 2 ;; *) shift ;; esac
done
TRAIN="$HARNESS_DIR/target/repo/train.py"
sed -i 's/from sklearn\.tree import DecisionTreeClassifier/from sklearn.ensemble import RandomForestClassifier/' "$TRAIN"
sed -i 's/clf = DecisionTreeClassifier(max_depth=2, random_state=42)/clf = RandomForestClassifier(n_estimators=100, random_state=42)/' "$TRAIN"
EOF
chmod +x "$MOCK_BIN/opencode"

_run_harness \
    && ok "harness.py run completed" \
    || fail "harness.py exited non-zero on improvement run"

LAST_IMPROVED=$(python3 -c "
import json, sys
events = [json.loads(l) for l in open(sys.argv[1]) if l.strip()]
iters = [e for e in events if e.get('event') == 'iteration']
print('yes' if iters and iters[-1].get('improved') else 'no')
" "$WORK/state/history.jsonl" 2>/dev/null || echo "error")
[[ "$LAST_IMPROVED" == "yes" ]] \
    && ok "last iteration records improved=true" \
    || fail "expected improved=true, got: $LAST_IMPROVED"

BEST_SCORE=$(python3 -c "
import json
print(json.load(open('$WORK/state/best.json'))['score'])
" 2>/dev/null || echo "0")
SCORE_IMPROVED=$(python3 -c "
print('yes' if float('$BEST_SCORE') > float('$BASELINE_SCORE') else 'no')
" 2>/dev/null || echo "no")
[[ "$SCORE_IMPROVED" == "yes" ]] \
    && ok "best.json score ($BEST_SCORE) > baseline ($BASELINE_SCORE)" \
    || fail "score did not improve: best=$BEST_SCORE  baseline=$BASELINE_SCORE"

grep -q "RandomForestClassifier" "$TRAIN_PY" \
    && ok "train.py committed with RandomForestClassifier" \
    || fail "train.py does not contain RandomForestClassifier after improvement"

# ── Test 4: regression reverted ────────────────────────────────────────────

info "Test 4: regression revert"

cat > "$MOCK_BIN/opencode" << 'EOF'
#!/usr/bin/env bash
HARNESS_DIR=""
while [[ $# -gt 0 ]]; do
    case "$1" in --dir) HARNESS_DIR="$2"; shift 2 ;; *) shift ;; esac
done
# Overwrite train.py with a script that outputs a deliberately terrible score.
printf '%s\n' \
    'import json' \
    'print(json.dumps({"score": 0.0001, "higher_is_better": True, "summary": "intentional regression"}))' \
    > "$HARNESS_DIR/target/repo/train.py"
EOF
chmod +x "$MOCK_BIN/opencode"

_run_harness \
    && ok "harness.py run completed" \
    || fail "harness.py exited non-zero on regression run"

LAST_IMPROVED=$(python3 -c "
import json, sys
events = [json.loads(l) for l in open(sys.argv[1]) if l.strip()]
iters = [e for e in events if e.get('event') == 'iteration']
print('yes' if iters and iters[-1].get('improved') else 'no')
" "$WORK/state/history.jsonl" 2>/dev/null || echo "error")
[[ "$LAST_IMPROVED" == "no" ]] \
    && ok "last iteration records improved=false" \
    || fail "expected improved=false, got: $LAST_IMPROVED"

grep -q "RandomForestClassifier" "$TRAIN_PY" \
    && ok "target/repo reverted to best state (RandomForestClassifier present)" \
    || fail "target/repo not reverted after regression"

FINAL_BEST=$(python3 -c "
import json
print(json.load(open('$WORK/state/best.json'))['score'])
" 2>/dev/null || echo "0")
BEST_UNCHANGED=$(python3 -c "
print('yes' if float('$FINAL_BEST') == float('$BEST_SCORE') else 'no')
" 2>/dev/null || echo "no")
[[ "$BEST_UNCHANGED" == "yes" ]] \
    && ok "state/best.json score unchanged after regression ($FINAL_BEST)" \
    || fail "state/best.json changed after regression: $FINAL_BEST ≠ $BEST_SCORE"

# ── Summary ────────────────────────────────────────────────────────────────

echo ""
TOTAL=$((PASS + FAIL))
if ((FAIL == 0)); then
    printf '\033[32m\033[1mAll %d tests passed.\033[0m\n' "$TOTAL"
    exit 0
else
    printf '\033[31m\033[1m%d/%d tests failed:\033[0m\n' "$FAIL" "$TOTAL"
    for err in "${ERRORS[@]}"; do
        printf '  \033[31m✗\033[0m  %s\n' "$err"
    done
    exit 1
fi
