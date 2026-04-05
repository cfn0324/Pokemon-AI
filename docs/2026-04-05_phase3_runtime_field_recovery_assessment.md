# 2026-04-05 Phase 3 Runtime Field Recovery Assessment

## 1. Scope

This round starts `Phase 3` with one bounded heavy task instead of expanding the experiment matrix:

- focus on Oak Lab / Pallet local deadlocks during real-AI runs
- improve runtime fallback behavior without reintroducing long scripted routes
- validate first with tests, then with one real-AI probe under the same protocol family used in Phase 2

## 2. Targeted Problem

Phase 2 evidence showed a repeated failure pattern:

- the run enters a short transport failure or cooldown window
- deterministic WAIT rewrites try one or two local movement recoveries
- after a short retreat loop, the only previously viable local step can become temporarily avoided
- once another direction fails, fallback degrades into long `api_unavailable_field_interaction` probing

This was visible in the Phase 2 repeated runs at positions such as:

- Oak's Lab `map 40, (8,11)`
- Pallet Town `map 0, (11,12)`

The thesis-level issue is not only "the model failed once", but that the runtime fallback amplified a local navigation mistake into a long non-productive recovery segment.

## 3. Engineering Changes

Code changes:

- `main.py`
  - added `_get_temporarily_avoided_field_recovery_decision`
  - deterministic fallback now retries a single previously successful non-warp direction before degrading into blind interaction probing
  - `wait_rewrite_*` directional moves now count as deterministic movement attempts for failed-move evidence, so blocked evidence is recorded earlier
- `tests/test_runtime_safeguards.py`
  - added coverage for the single-direction recovery case
  - added coverage for failed-move recording from `wait_rewrite_ai_cooldown`

Design intent:

- keep temporary avoidance protections intact for ambiguous multi-direction loops
- only reopen a temporarily avoided direction when it is the single remaining non-warp locally validated path
- reduce fallback degeneration without turning the runtime layer back into a hidden script

## 4. Validation

### 4.1 Automated tests

- `pytest tests/test_runtime_safeguards.py -q`
  - result: `75 passed`
- `pytest -q`
  - result: `288 passed, 1 warning`

### 4.2 Real-AI probe

Command family:

```powershell
python scripts/autonomous_smoke.py `
  --checkpoint checkpoint_195913 `
  --turns 120 `
  --llm-primary `
  --ai-full-control `
  --reset-context `
  --decision-max-tokens 384 `
  --action-plan-max-actions 3 `
  --output tmp/phase3_field_recovery_probe.json
```

Generated artifacts:

- raw report: `tmp/phase3_field_recovery_probe.json`
- standardized summary: `docs/thesis_logs/2026-04-05_phase3_field_recovery_probe.md`

Observed results:

- `fatal_error = null`
- `timeline_valid = true`
- `ai_dominant = true`
- `ai_authored_ratio = 0.7000`
- `main_model_ratio = 0.6083`
- `fallback_turns = 0`
- `api_unavailable_field_interaction = 0`
- `api_unavailable_field_recovery = 0`
- final position: `map 0, (4,2)`

Most important interpretation:

- this probe no longer collapsed into the long `api_unavailable_field_interaction` tail seen in Phase 2 negative cases
- the runtime remained productive through cooldown/error windows using ordinary field movement and planner escapes
- the run still did **not** reach `Route 1`, `got_pokedex`, or `oak_got_parcel`

## 5. Phase Judgment

This round should be judged as:

- `Phase 3`: started
- current subtask: successful
- overall phase: not complete

Why it counts as a real improvement:

- it removes one concrete runtime amplifier of Oak Lab / Pallet deadlocks
- it improves the credibility of later real-AI experiments by reducing fallback-only stagnation
- it does not inflate claims beyond the current evidence

Why Phase 3 is still incomplete:

- the project still lacks stronger story milestones after this fix
- the model still spends too many turns in weak local exploration around Pallet Town after leaving the lab
- this round improves recovery quality, but not yet the model's early-story objective selection

## 6. Next Recommended Heavy Task

The next bounded Phase 3 task should stay narrow:

- analyze why the real-AI probe reaches Pallet Town north-edge / fence-adjacent weak loops without committing to the Route 1 trigger
- prioritize improving local decision support around top-of-town route approach and Oak-trigger interpretation
- avoid expanding to broad ablation or thesis-figure work before a stronger milestone is reached
