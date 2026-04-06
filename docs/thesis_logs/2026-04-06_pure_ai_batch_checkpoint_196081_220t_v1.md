# 2026-04-06 Pure-AI Batch Checkpoint 196081 220T V1

Artifacts:

- summary markdown: `tmp/real_ai_batches/2026-04-06_pure_ai_batch_checkpoint_196081_220t_v1/2026-04-06_pure_ai_batch_checkpoint_196081_220t_v1_summary.md`
- summary json: `tmp/real_ai_batches/2026-04-06_pure_ai_batch_checkpoint_196081_220t_v1/2026-04-06_pure_ai_batch_checkpoint_196081_220t_v1_summary.json`
- manifest: `tmp/real_ai_batches/2026-04-06_pure_ai_batch_checkpoint_196081_220t_v1/2026-04-06_pure_ai_batch_checkpoint_196081_220t_v1_manifest.json`

Protocol:

- checkpoint: `checkpoint_196081`
- turns per run: `220`
- runs: `3`
- mode: `pure-llm`
- runtime fallback disabled: `yes`
- reset context: `yes`

Aggregate:

- reports: `3`
- completed requested turns: `3/3`
- AI-dominant reports: `3/3`
- `reached_route1`: `3/3`
- `reached_viridian_city`: `1/3`
- `entered_viridian_mart`: `1/3`
- `obtained_oaks_parcel`: `0/3`

Per-run table:

| Run | Best milestone | AI authored ratio | AI avg latency (s) | AI max latency (s) | `ai_error` turns | `ai_cooldown` turns | Transport-failure log lines | Notes |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `run01` | `reached_route1` | 72.73% | 6.363 | 30.451 | 5 | 55 | 42 | ended inside Route 1 battle state |
| `run02` | `reached_route1` | 78.18% | 5.148 | 22.397 | 4 | 44 | 29 | ended inside Route 1 battle state |
| `run03` | `entered_viridian_mart` | 64.55% | 5.987 | 14.575 | 7 | 71 | 38 | best repeated-batch progress |

Interpretation:

- this is the first new repeated pure-AI batch in the current no-runtime-fallback protocol that repeatedly reaches at least `Route 1` and once reaches `Viridian Mart`
- the dominant external failure mode is transport instability, not deterministic takeover
- because `fallback_ratio = 0` in all three runs, these logs can be cited as direct evidence that the system remains AI-owned even when API connectivity is unstable

