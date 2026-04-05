# 2026-04-05 Phase 3 Story Guidance Assessment

## 1. Scope

This round continues `Phase 3` with a second bounded heavy task:

- keep `ai_full_control_mode = true`
- do not restore the fixed-route controller into the runtime stage chain
- instead, strengthen the state text so the model better understands the early-story objective after the first rival battle

The concrete target is the Pallet Town north-exit / Route 1 trigger area, which remained the next obvious bottleneck after the runtime field-recovery fix.

## 2. Problem

The previous Phase 3 runtime-recovery probe removed the long fallback deadlock, but the run still failed to leave Pallet Town.

Observed failure pattern:

- the agent could reach the north edge of Pallet Town
- it could sometimes stand directly below the Route 1 grass opening
- but it still treated side-town frontier tiles as equally valid exploration targets
- as a result, the model drifted laterally instead of committing to the Route 1 entrance

This is an AI-decision-quality problem, not a fallback-resilience problem:

- there was no long `api_unavailable_field_interaction` tail anymore
- the issue was that the prompt still framed the scene mostly as generic frontier exploration

## 3. Engineering Changes

Code changes:

- `src/state/game_state.py`
  - added `_build_story_guidance`
  - the state now emits narrow early-story cues for the `post_battle_intro_route` arc
  - these cues are rendered into a new `STORY GUIDANCE` section in `get_text_representation`

Design constraints:

- no hidden scripted takeover
- no re-enabling `post_battle_intro_route` under `ai_full_control_mode`
- only high-level objective shaping, with special emphasis on:
  - leaving Oak's Lab
  - routing around the lab fence toward the northbound path
  - prioritizing `UP` when aligned under Pallet Town's north grass opening

Tests added/updated:

- `tests/test_game_state.py`
  - story guidance appears for the Pallet north-exit state
  - story guidance does not appear after parcel/Pokedex progression
  - text rendering includes the new guidance section

## 4. Validation

### 4.1 Automated tests

- `pytest tests/test_game_state.py tests/test_runtime_safeguards.py -q`
  - result: `82 passed`
- `pytest -q`
  - result: `291 passed, 1 warning`

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
  --output tmp/phase3_story_guidance_probe.json
```

Generated artifacts:

- raw report: `tmp/phase3_story_guidance_probe.json`
- standardized summary: `docs/thesis_logs/2026-04-05_phase3_story_guidance_probe.md`

Observed results:

- `fatal_error = null`
- `timeline_valid = true`
- `ai_dominant = true`
- `main_model_ratio = 0.7500`
- `ai_authored_ratio = 0.8917`
- `fallback_turns = 0`
- `api_unavailable_field_interaction = 0`
- `reached_route1 = true`
- final position: `map 12, (11,32)` in battle

Most important interpretation:

- the run no longer stopped at Pallet Town's north edge
- the model committed to the north opening and crossed into Route 1
- this is materially stronger than the previous Phase 3 probe, which remained in Pallet Town and ended at `map 0, (4,2)`

## 5. Comparison Against The Previous Phase 3 Probe

Previous probe (`tmp/phase3_field_recovery_probe.json`):

- `reached_route1 = false`
- `main_model_ratio = 0.6083`
- `ai_authored_ratio = 0.7000`
- final position: `map 0, (4,2)`

Current probe (`tmp/phase3_story_guidance_probe.json`):

- `reached_route1 = true`
- `main_model_ratio = 0.7500`
- `ai_authored_ratio = 0.8917`
- final position: `map 12, (11,32)`

This means the second bounded Phase 3 change improved both:

- story-progress strength
- AI ownership ratio

without needing additional deterministic route takeovers.

## 6. Phase Judgment

Current judgment after this round:

- `Phase 3`: meaningfully advanced
- Oak Lab / Pallet local deadlock problem: reduced
- Pallet north-exit objective confusion: reduced
- stronger early-story milestone: reached `Route 1`
- overall phase: still not complete

Why Phase 3 is still incomplete:

- the run still did not reach `got_oaks_parcel`, `oak_got_parcel`, or `got_pokedex`
- the latest probe ended inside an early wild battle on Route 1
- the next bottleneck is shifting from Pallet exit commitment to Route 1 battle-and-continuation efficiency

## 7. Next Recommended Heavy Task

The next bounded Phase 3 task should focus on the new bottleneck exposed by this run:

- improve Route 1 early-battle / post-battle progress quality under AI-led play
- reduce excessive turn spending on battle intro / battle text progression
- preserve AI ownership while making early Route 1 continuation more reliable toward Viridian City and Oak's Parcel
