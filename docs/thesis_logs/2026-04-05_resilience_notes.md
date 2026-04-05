# 2026-04-05 Resilience Notes

## Runtime configuration

- Checkpoint: `checkpoint_195913`
- Mode: `--llm-primary`
- AI environment:
  - `AI_API_KEY=dummy`
  - `AI_BASE_URL=http://localhost`
  - `AI_MODEL=dummy`

## What improved in this iteration

- Unreachable AI transport errors no longer burn large same-turn retry budgets before falling back.
- Field control now filters stale `battle` and stale `menu_active` classifications more safely.
- Post-blackout deterministic routing can recover back through Pallet, Route 1, Route 2, and the Viridian Forest approach.
- Early solo-starter battles now have a stall-recovery path that can reselect a usable move when the default move runs out of PP.
- Temporarily avoided trigger-tile moves now actually stay out of retryable local exploration choices.
- API-unavailable dialogue handling now has:
  - stable-UI recovery for repeated no-progress `A` loops
  - short dialogue-exit movement recovery so a just-closed dialogue is less likely to be reopened immediately

## Validation outcome

- `1800` turns: completed, no fatal error, recovered from blackout and resumed the deterministic route.
- `2600` turns: completed, no fatal error, reached Route 1 state again after resolving a forest-side dialogue/battle trap, final state remained playable.
- `4000` turns: completed, no fatal error, Charmander reached level `10`, final state remained in Viridian Forest with healthy HP and active exploration instead of a fixed deadlock.

## Current thesis-relevant interpretation

- The project is now meaningfully more robust under AI-unavailable conditions.
- The runtime can survive several previously catastrophic failure modes and continue autonomous play for thousands of turns.
- The strongest evidence is not merely unit-test success; it is that long headless runs now finish on time and remain in playable, non-crashed states.

## Remaining gaps

- The system still spends too many turns inside Viridian Forest before making northbound story progress.
- No badge has been obtained yet in the long validation runs, so the current evidence supports early-game feasibility, not full-game autonomy.
- Dialogue-trigger tiles and certain wild-battle sub-states still consume too many turns before recovery logic wins.
- The strongest remaining engineering target is better forest traversal and exit acquisition, not basic crash recovery.
