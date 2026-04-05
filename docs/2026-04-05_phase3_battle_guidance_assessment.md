# 2026-04-05 Phase 3 Battle Guidance Assessment

## 1. Scope

This round continues `Phase 3` with a third bounded heavy task:

- keep `ai_full_control_mode = true`
- do not restore deterministic early-battle ownership into the runtime stage chain
- improve Route 1 battle decision quality through state/prompt shaping rather than hidden takeover
- keep the smoke evaluation protocol usable when short-lived provider/token outages occur

The concrete target is the first wild Route 1 battle that became the new bottleneck after Pallet north-exit guidance was added.

## 2. Problem

After the previous `Phase 3` story-guidance change:

- the agent could reach `Route 1`
- but the run still ended inside the first wild battle
- many turns were spent on intro text / send-out text before the model committed to a real battle choice

During the first follow-up probes, two additional issues became visible:

- the state could still describe a `known_exit` as an immediate preference even after repeated local failures from that tile
- smoke evaluation could be polluted by provider-side `status 500: 没有可用 token`, which triggered a long cooldown and let fallback consume the whole battle segment

This meant the next heavy task had to improve both:

- AI-readable battle decision cues
- evaluation stability for short bounded real-AI probes

## 3. Engineering Changes

### 3.1 Battle-state and prompt shaping

Code changes:

- `src/state/game_state.py`
  - added move naming / tactical tagging for party moves
  - added `_build_battle_guidance`
  - rendered a new `BATTLE GUIDANCE` section in `get_text_representation`
  - battle guidance now distinguishes:
    - active battle text
    - command / move menu handling
    - preferred damaging move slot
    - low-HP caution
  - navigation cues now mark previously successful routes as currently blocked when local repeated failures occur, for example `known_exit_but_currently_blocked`

- `src/agents/main_agent.py`
  - prompt now explicitly tells the model to treat `BATTLE GUIDANCE` as the highest-priority local cue during battles
  - prompt now reinforces:
    - choose `FIGHT` on the standard early-game battle menu
    - follow the preferred damaging move slot when named in state text

### 3.2 Smoke-evaluation cooldown alignment

Code changes:

- `scripts/autonomous_smoke.py`
  - aligned smoke-mode API cooldown settings so:
    - ordinary API cooldown stays short
    - persistent provider/token cooldown is also short in smoke mode
    - unreachable transport cooldown is also short in smoke mode

This change is intentionally evaluation-scoped:

- it improves bounded real-AI probe recovery
- it does not change the default long-form runtime policy in `config.yaml`

### 3.3 Tests added / updated

- `tests/test_game_state.py`
  - battle guidance prefers `FIGHT` and the first damaging move
  - post-battle dialogue guidance is emitted correctly
  - rendered text includes move labels and `BATTLE GUIDANCE`
  - repeated local failures on a formerly valid route now render as `known_exit_but_currently_blocked`

- `tests/test_main_agent_api_failures.py`
  - persistent provider errors can use short smoke cooldowns when configured that way

## 4. Validation

### 4.1 Automated tests

- `pytest tests/test_game_state.py tests/test_main_agent_api_failures.py tests/test_runtime_safeguards.py -q`
  - result: `95 passed`
- `pytest -q`
  - result: `296 passed, 1 warning`

### 4.2 Intermediate probe: battle-quality change initially polluted by provider cooldown

Intermediate artifact:

- raw report: `tmp/phase3_battle_guidance_probe_retry.json`

Observed facts:

- `reached_route1 = true`
- a provider-side `status 500: 没有可用 token` occurred mid-run
- the run then spent the battle segment inside long `ai_cooldown` / `api_unavailable_battle_fallback`

Interpretation:

- Route 1 reachability remained strong
- but that run could not serve as a clean battle-guidance assessment

### 4.3 Clean real-AI probe after smoke cooldown alignment

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
  --output tmp/phase3_battle_guidance_probe_shortcooldown.json
```

Generated artifacts:

- raw report: `tmp/phase3_battle_guidance_probe_shortcooldown.json`
- standardized summary: `docs/thesis_logs/2026-04-05_phase3_battle_guidance_probe.md`

Observed results:

- `fatal_error = null`
- `timeline_valid = true`
- `ai_dominant = true`
- `main_model_ratio = 0.7083`
- `ai_authored_ratio = 0.8417`
- `fallback_turns = 0`
- `reached_route1 = true`
- `reached_viridian_city = false`
- final position: `map 12, (11,33)` in battle

Most important timeline evidence:

- the Route 1 battle segment stayed AI-owned rather than fallback-owned
- at turn `196025`, the model selected `FIGHT`
- at turn `196026`, the model selected `Scratch`

This is the key new evidence from this round:

- the project no longer only shows “AI reaches Route 1 and gets stuck in battle”
- it now shows “AI reaches Route 1 and makes the correct first actionable battle decisions”

## 5. Comparison Against The Previous Phase 3 Probe

Previous clean probe (`tmp/phase3_story_guidance_probe.json`):

- `reached_route1 = true`
- `fallback_turns = 0`
- ended in battle before a clear command-menu resolution was observed

Current clean probe (`tmp/phase3_battle_guidance_probe_shortcooldown.json`):

- `reached_route1 = true`
- `fallback_turns = 0`
- AI explicitly selected `FIGHT`
- AI explicitly selected `Scratch`

Interpretation:

- AI ownership ratio stayed high enough to remain `ai_dominant`
- battle-decision quality is stronger than the previous Route 1 probe even though total progress still ends inside battle text

## 6. Phase Judgment

Current judgment after this round:

- `Phase 3`: meaningfully advanced again
- Oak Lab local cue contradictions: reduced
- Pallet north-exit commitment: still retained
- Route 1 first actionable battle choice: improved
- overall phase: still not complete

Why `Phase 3` is still incomplete:

- the clean probe still did not reach `Viridian City`
- it did not obtain `Oak's Parcel`
- it did not reach `got_pokedex`
- the battle still spends many turns on intro / result text before the next exploration segment resumes

## 7. Next Recommended Heavy Task

The next bounded `Phase 3` task should focus on the remaining Route 1 bottleneck:

- reduce excessive turns spent on battle intro / result text progression
- improve post-battle continuation quality so the run more reliably exits the battle and keeps moving toward `Viridian City`
- preserve AI ownership while making the early Route 1 to Viridian transition more reliable
