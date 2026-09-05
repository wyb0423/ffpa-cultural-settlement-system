# Static Contract Repairs

## Scope

Repair the verified differences between the documented settlement contract and the current implementation without changing stable save variables or generated province data.

## Behavior

- Sponsors may be recognized or unrecognized countries, but never decentralized countries.
- Targets must be decentralized countries; unrecognized countries are not valid targets.
- A project is cancelled on its next monthly evaluation if its original target owner changes, the target stops being decentralized, the cultural homeland condition fails, the sponsor stops being recognized or unrecognized, loses both Colonial Resettlement and Frontier Colonization or loses Colonization technology, becomes hostile to the target, or loses both land adjacency and the coastal-port route.
- Strategic-region interest is required only when starting a project. Losing it does not cancel an active project.
- Province phases remain at 25, 50, 75 and 95 progress. At 100, the reserved final province is transferred and the state becomes unincorporated.

## Changes

- Narrow the diplomatic-action target and state-owner gates to decentralized countries and remove the now-dead target-subject check.
- Extend the existing monthly validity trigger with the target-type and route checks. Do not introduce a new persistent identifier or an unproven variable-as-scripted-argument pattern.
- Correct the phase-threshold documentation and remove the invalid UTF-16/NUL suffix from `README.md`.
- Extend `tools/validate_mod.py` with narrow regression checks for the target restriction, monthly route check, 95-point fourth phase and NUL-free text files.

## Verification

Run the existing local validator, parameterized final-stack validator, generated-data double-run comparison and `git diff --check`. Runtime loading, dispatch and retained-state behavior remain subject to the existing in-game test matrix.
