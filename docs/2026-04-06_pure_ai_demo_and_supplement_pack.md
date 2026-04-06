# 2026-04-06 Pure-AI Demo And Supplement Pack

## 1. Asset package

### 1.1 Videos

- `docs/report_assets/2026-04-06_pure_ai_demo/videos/pure_ai_demo_v4.mp4`
  - Current best presentation video.
  - Pure AI decisions.
  - Runtime fallback disabled.
  - Screenshot overlay disabled.
  - Reaches `Oak's Lab -> Pallet Town -> Route 1 -> Viridian City -> Viridian Mart`, then obtains `Oak's Parcel`.
- `docs/report_assets/2026-04-06_pure_ai_demo/videos/pure_ai_demo_v3_condensed.mp4`
  - Backup condensed version.
- `docs/report_assets/2026-04-06_pure_ai_demo/videos/pure_ai_demo_v3.mp4`
  - Earlier non-condensed no-overlay capture.
- `docs/report_assets/2026-04-06_pure_ai_demo/videos/pure_ai_demo_v2.mp4`
  - Earlier version kept only for comparison; contains the old green overlay artifact.

### 1.2 Reports

- `docs/report_assets/2026-04-06_pure_ai_demo/reports/pure_ai_latest_120_v4.json`
- `docs/report_assets/2026-04-06_pure_ai_demo/reports/pure_ai_latest_260_v7.json`
- `docs/report_assets/2026-04-06_pure_ai_demo/reports/pure_ai_latest_320_v6.json`
- `docs/report_assets/2026-04-06_pure_ai_demo/reports/pure_ai_batch_220_summary.json`
- `docs/report_assets/2026-04-06_pure_ai_demo/reports/pure_ai_batch_220_summary.md`
- `docs/report_assets/2026-04-06_pure_ai_demo/reports/pure_ai_batch_220_manifest.json`

### 1.3 Figures

- Raw keyframes: `docs/img/2026-04-06/demo_run_220/raw/`
- Main figures: `docs/img/2026-04-06/main_figures/`

## 2. Evidence update for the latest pure-AI checkpoint

### 2.1 Single-run evidence

| Evidence | Protocol | Best milestone | AI authored ratio | Fallback ratio | Notes |
| --- | --- | --- | ---: | ---: | --- |
| `tmp/pure_ai_latest_120_v4.json` | `pure-llm + disable-runtime-fallbacks` | `reached_route1` | 100.00% | 0.00% | Clean short proof that the latest checkpoint no longer loops in Oak's Lab / Pallet Town. |
| `tmp/pure_ai_latest_260_v7.json` | `pure-llm + disable-runtime-fallbacks` | `reached_viridian_city` | 83.46% | 0.00% | First clean single-run proof that pure AI reaches Viridian City under the new protocol. |
| `docs/report_assets/2026-04-06_pure_ai_demo/videos/pure_ai_demo_v4.mp4` | `capture_evidence_run.py`, `220 turns`, same protocol | `obtained_oaks_parcel` | N/A in capture script | 0.00% runtime takeover | Best presentation artifact. It visibly reaches Viridian Mart and gets `Oak's Parcel`, but still shows a post-parcel mart loop that should be described as a failure case, not hidden. |
| `tmp/pure_ai_latest_320_v6.json` | `pure-llm + disable-runtime-fallbacks` | `reached_route1` | 88.75% | 0.00% | Useful for long-run latency / transport-failure evidence. |

### 2.2 New repeated batch

Batch artifact:

- `tmp/real_ai_batches/2026-04-06_pure_ai_batch_checkpoint_196081_220t_v1/`
- mirrored summary: `docs/report_assets/2026-04-06_pure_ai_demo/reports/pure_ai_batch_220_summary.json`

Protocol:

- checkpoint: `checkpoint_196081`
- turns: `220`
- runs: `3`
- mode: `pure-llm`
- `decision.disable_runtime_fallbacks = true`
- `reset_context = true`

Per-run summary:

| Run | Best milestone | AI authored ratio | Fallback ratio | Avg latency (s) | Max latency (s) | Decision-source note |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| `run01` | `reached_route1` | 72.73% | 0.00% | 6.363 | 30.451 | `ai=160`, `ai_error=5`, `ai_cooldown=55` |
| `run02` | `reached_route1` | 78.18% | 0.00% | 5.148 | 22.397 | `ai=172`, `ai_error=4`, `ai_cooldown=44` |
| `run03` | `entered_viridian_mart` | 64.55% | 0.00% | 5.987 | 14.575 | `ai=142`, `ai_error=7`, `ai_cooldown=71` |

Aggregate summary:

- repeated batch count: `3`
- `reached_route1`: `3/3`
- `reached_viridian_city`: `1/3`
- `entered_viridian_mart`: `1/3`
- `obtained_oaks_parcel`: `0/3`
- AI-dominant reports: `3/3`
- deterministic-tool ratio: `0.00%`
- fallback ratio: `0.00%`

Conclusion:

- this batch satisfies the required new real-AI repeated-batch evidence for `Viridian City`-level progress
- it does **not** yet satisfy repeated-batch evidence for stable `Oak's Parcel`
- therefore the thesis can now claim repeated pure-AI progress to `Viridian City / Viridian Mart`, but should still avoid claiming repeated stable parcel completion

## 3. Formal supplement tables

### 3.1 Ablation table

The table below is not a full factorial from scratch. It is a defensible thesis-facing consolidation of the most relevant existing artifacts plus the new pure-AI evidence.

| Configuration | Story guidance | Battle guidance | `llm_primary` | `ai_full_control` | Runtime fallback disabled | Evidence | Best milestone | AI authored ratio | Fallback ratio |
| --- | --- | --- | --- | --- | --- | --- | --- | ---: | ---: |
| Phase-2 retry-fixed baseline | No | No | Yes | Yes | No | `2026-04-05_phase2_real_ai_baseline_retryfix_summary.json` | `entered_oaks_lab` | 30.00% avg | 52.78% avg |
| Story-guidance probe | Yes | No | Yes | Yes | No | `tmp/phase3_story_guidance_probe.json` | `reached_route1` | 89.17% | 0.00% |
| Story + battle-guidance probe | Yes | Yes | Yes | Yes | No | `tmp/phase3_battle_guidance_probe_shortcooldown.json` | `reached_route1` | 84.17% | 0.00% |
| Pure-AI latest checkpoint | Yes | Yes | No | No | Yes | `tmp/pure_ai_latest_260_v7.json` | `reached_viridian_city` | 83.46% | 0.00% |

Interpretation:

- the biggest structural gain comes from adding early-story guidance; without it, the system often never exits the Oak Lab regime
- battle guidance mainly improves battle ownership and reduces brittle battle fallback behavior, but it does not by itself solve the Oak Lab / Pallet route problem
- the strongest thesis-facing setting is now the pure-AI, no-runtime-fallback protocol because it removes the ambiguity that deterministic runtime recovery is secretly carrying the demo

### 3.2 Cost and latency table

| Evidence | Avg AI latency (s) | Max AI latency (s) | Provider failure logs | Transport failure logs | Fallback turn ratio |
| --- | ---: | ---: | ---: | ---: | ---: |
| `tmp/pure_ai_latest_120_v4.json` | 4.284 | 12.412 | N/A in JSON-only artifact | 0 observed in decision counts | 0.00% |
| `tmp/pure_ai_latest_260_v7.json` | 5.603 | 44.277 | N/A in JSON-only artifact | `ai_error=2`, `ai_cooldown=41` turns | 0.00% |
| `tmp/pure_ai_latest_320_v6.json` | 4.415 | 14.847 | N/A in JSON-only artifact | `ai_error=3`, `ai_cooldown=33` turns | 0.00% |
| `2026-04-06_pure_ai_batch_checkpoint_196081_220t_v1` | 5.809 weighted avg | 30.451 | 0 | 109 `AI request transport failure` log lines; 211 `ConnectionResetError` mentions; 5 `SSLEOFError` mentions | 0.00% |

Interpretation:

- the new pure-AI protocol successfully holds `fallback_ratio = 0`, but this does **not** mean provider/network instability disappeared
- instead, instability now manifests as `ai_error` / `ai_cooldown` turns and latency spikes
- the thesis should explicitly say that runtime fallback was disabled for these runs, so API instability is now visible in the report rather than hidden inside deterministic takeover

### 3.3 Higher-quality main figures

New figures prepared in `docs/img/2026-04-06/main_figures/`:

- `fig01_pallet_west_lane.png`
- `fig02_pallet_north_exit.png`
- `fig03_route1_northbound.png`
- `fig04_viridian_mart_parcel.png`
- `fig05_post_parcel_mart_loop.png`
- `fig06_pure_ai_demo_progression.png`
- `fig07_decision_chain_annotation.png`
- `fig08_method_positioning.png`

Recommended main-text usage:

- main result figure: `fig06_pure_ai_demo_progression.png`
- method explanation figure: `fig07_decision_chain_annotation.png`
- method positioning figure: `fig08_method_positioning.png`
- failure-case figure: `fig05_post_parcel_mart_loop.png`

### 3.4 Heuristic baseline comparison

No controlled human-subject protocol was run in this turn. To satisfy the baseline requirement without inventing unsupported human data, use a conservative **heuristic route budget** derived from the existing scripted route logic in:

- `src/control/post_battle_intro_route.py`
- `src/control/viridian_parcel_controller.py`

Heuristic route budget:

- Oak's Lab exit from the restored checkpoint: about `4` field moves
- Pallet Town lab frontage to Route 1 alignment: about `14` field moves
- Route 1 south entrance to Viridian south gate: about `58` field moves
- Viridian south gate to Viridian Mart doorway: about `36` field moves
- total to Viridian Mart doorway: about `112` field moves, excluding mandatory clerk-dialogue confirmation presses

Comparison table:

| Milestone | Heuristic reference | Current best pure-AI evidence | Gap |
| --- | ---: | ---: | --- |
| Route 1 entry | about `18-20` turns from checkpoint | `36` turns in the new batch path | about `1.8x-2.0x` slower |
| Viridian City south gate | about `76` field moves from checkpoint | `198` turns in `pure_ai_latest_260_v7.json` | about `2.6x` slower |
| Viridian Mart doorway | about `112` field moves from checkpoint | within the successful `220`-turn demo run | still materially slower and more fragile |
| Oak's Parcel obtained | doorway budget + dialogue overhead | achieved once in `pure_ai_demo_v4.mp4`, not yet in repeated batch | milestone reached, but not yet robust |

Thesis-safe interpretation:

- the system now demonstrates genuine pure-AI milestone progress
- it is still substantially less efficient than a hand-scripted heuristic route
- therefore the current claim should be "autonomous progress with visible reasoning and real runtime constraints", not "human-level efficiency"

## 4. Strongly recommended supplement items

### 4.1 Failure taxonomy

| Failure class | Symptom | Example evidence | Current status |
| --- | --- | --- | --- |
| Provider failure | server-side refusal such as `status 500` / `没有可用token`, often followed by cooldown or fallback in older protocols | historical discussion in `docs/2026-04-05_phase3_battle_guidance_assessment.md` | still relevant historically, but not the dominant failure in the newest batch |
| Transport failure | `ConnectionResetError`, `SSLEOFError`, repeated `AI request transport failure`, then many `ai_cooldown` turns | `2026-04-06_pure_ai_batch_checkpoint_196081_220t_v1/*.out` | dominant external failure mode in the newest repeated batch |
| Oak Lab local loop | AI drifts left of the door columns or re-explores the lab instead of aligning with the exit | pre-fix `pure_ai_latest_60_v2.json`, phase-2 baseline docs | substantially reduced after exact Oak Lab story guidance and turn-in-place handling |
| Battle intro stall | long sequences of battle-text advancement or provider-induced wait loops around early Route 1 battles | `tmp/pure_ai_latest_320_v6.json` | still visible under poor API conditions |
| Post-parcel mart loop | item already acquired, but the run still oscillates inside Viridian Mart instead of exiting cleanly | `pure_ai_demo_v4.mp4`, `fig05_post_parcel_mart_loop.png` | current most important local gameplay bug |

### 4.2 Method positioning

Use `docs/img/2026-04-06/main_figures/fig08_method_positioning.png` as the thesis-facing positioning figure:

- left: RL agents
- middle: generative agents
- right: this hybrid runtime agent

Recommended wording:

> The system is not an end-to-end reinforcement learner and not a pure sandboxed generative agent. It is a hybrid runtime agent: a live-state grounded LLM decision loop operating under explicit runtime safeguards, evaluation scripts, and evidence-first reporting.

### 4.3 Reproducibility checklist

Environment:

- git commit: `6aa32d4`
- Python: `3.13.5`
- pytest: `8.3.5`
- ffmpeg: `7.0.2-full_build-www.gyan.dev`
- AI endpoint in the recorded batch manifest: `https://api.ququ233.com/v1`
- AI model in the recorded batch manifest: `gpt-5.4`

Core commands used for this update:

```powershell
pytest tests/test_runtime_safeguards.py tests/test_async_runtime.py tests/test_game_state.py tests/test_main_agent_prompting.py -q
```

```powershell
python scripts/autonomous_smoke.py --checkpoint checkpoint_196081 --turns 320 --pure-llm --disable-runtime-fallbacks --reset-context --output tmp\pure_ai_latest_320_v6.json
```

```powershell
python scripts/autonomous_smoke.py --checkpoint checkpoint_196081 --turns 260 --pure-llm --disable-runtime-fallbacks --reset-context --same-turn-budget 60 --output tmp\pure_ai_latest_260_v7.json
```

```powershell
python scripts/autonomous_smoke_batch.py --checkpoint checkpoint_196081 --turns 220 --runs 3 --label 2026-04-06_pure_ai_batch_checkpoint_196081_220t_v1 --pure-llm --disable-runtime-fallbacks --reset-context --ai-timeout 25 --same-turn-budget 30 --decision-max-tokens 448 --action-plan-max-actions 3
```

```powershell
python scripts/capture_evidence_run.py --checkpoint checkpoint_196081 --turns 220 --screenshot-dir tmp\evidence_pure_ai_demo_v4 --disable-visualizer --headless --pure-llm --disable-runtime-fallbacks --reset-context
```

```powershell
ffmpeg -y -framerate 10 -i tmp\evidence_pure_ai_demo_v4_dedup\frame_%04d.png -vf "scale=640:576:flags=neighbor" -c:v libx264 -preset medium -crf 18 -pix_fmt yuv420p tmp\pure_ai_demo_v4.mp4
```

Output files to cite:

- repeated batch: `tmp/real_ai_batches/2026-04-06_pure_ai_batch_checkpoint_196081_220t_v1/`
- best presentation video: `docs/report_assets/2026-04-06_pure_ai_demo/videos/pure_ai_demo_v4.mp4`
- main pure-AI city proof: `docs/report_assets/2026-04-06_pure_ai_demo/reports/pure_ai_latest_260_v7.json`

## 5. Thesis wording guardrails

Claims that are now safe:

- “the latest checkpoint can be advanced by pure AI without runtime fallback takeover”
- “single-run evidence reaches Viridian City and Viridian Mart, and one presentation run obtains Oak's Parcel”
- “a new repeated batch shows non-trivial reproducibility to Viridian City / Viridian Mart”

Claims that are still unsafe:

- “Oak's Parcel is repeated-batch stable”
- “the system is human-level efficient”
- “provider/network instability has been solved”
