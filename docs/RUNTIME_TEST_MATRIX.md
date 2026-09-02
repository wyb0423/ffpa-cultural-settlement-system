# Runtime Test Matrix

## Purpose

Static validation proves file structure and final-database assumptions. It does not prove that the engine merged an `INJECT`, dispatched an on-action, accepted a scope transition or retained the final state after later-loaded content. Run this matrix with the authoritative load order:

1. `[1.13] Tech & Res`
2. `2050: The Fire Falls`
3. `2050 Firefall — Core Balance Adapter`
4. `FFPA — Cultural Settlement System`

Use a disposable save. Do not benchmark performance while diagnostic logging is enabled.

## Preflight

Run local validation:

```powershell
py -3 tools\validate_mod.py
```

Run final-stack validation by supplying installation paths as arguments. Paths are development inputs and must not be written into portable Mod data:

```powershell
py -3 tools\validate_mod.py `
  --game-root '<Victoria 3 game data root>' `
  --tech-res-root '<Tech & Res root>' `
  --firefall-root '<Firefall root>' `
  --core-balance-root '<Core Balance root>'
```

The final-stack result must report:

- a negative colonial-growth remainder after the conservative positive-source bound;
- exact Core Balance AI token parity plus one Colonial Resettlement law gate;
- the expected final upstream law and company-charter providers.

## Diagnostic switch

With the game in debug mode, enable lifecycle logging from the console:

```text
effect set_global_variable = ffcs_debug_enabled_v1
```

Disable it immediately after the functional test:

```text
effect remove_global_variable = ffcs_debug_enabled_v1
```

`ffcs_debug_enabled_v1` is a test-only global switch, not a supported save interface. Enabled logging emits only for countries and states already carrying FFCS work. Search `game.log` and its rotated files for `FFCS|`.

Expected lifecycle markers:

```text
FFCS|CANDIDATE_CREATED
FFCS|SCHEDULER_REACHED
FFCS|EVALUATION_PASSED / FFCS|EVALUATION_FAILED
FFCS|EFFECT_APPLIED / FFCS|CANCELLED
```

## Gate A — Native Establish Colony

### Colonial Resettlement

1. Use a recognized country with Colonial Resettlement, Colonization technology and at least one Colonial Affairs level.
2. Select a state that would otherwise be colonizable.
3. Confirm that **Establish Colony** is invalid before execution with the no-colonial-growth reason.
4. Attempt the command and advance one day.
5. Confirm that no seed province, native colony marker or company colony was created.

### Control law

Repeat with Colonial Exploitation or Frontier Colonization. Establish Colony must become valid when all ordinary requirements are met. This distinguishes an FFCS law gate from a global colonization failure.

## Gate B — Company colonization charter

1. Use a company eligible for `colonization_charter` under ordinary vanilla conditions.
2. Under Colonial Resettlement, confirm that the charter is unavailable and displays the FFCS law explanation.
3. Confirm that AI cannot grant it during an observer run.
4. Switch to a control colonization law and confirm that the original unrecognized-owner and company eligibility rules still apply.

## Gate C — Cultural target restriction

For the same sponsor, prepare two otherwise equivalent target states:

- positive: homeland of at least one sponsor primary culture;
- negative: not a homeland of any sponsor primary culture.

The custom diplomatic action must list/select only the positive state. Repeat once for a player and once for AI. A negative state receiving a project is a release blocker even if it later cancels.

## Lifecycle and cleanup

For one valid project, confirm in order:

1. `CANDIDATE_CREATED` appears once;
2. the target owner emits `SCHEDULER_REACHED` on the monthly pulse;
3. the state emits `EVALUATION_PASSED` and advances;
4. province ownership changes at the four phase thresholds;
5. completion emits `EFFECT_APPLIED` and leaves an unincorporated state;
6. sponsor active and target inbound counters return to zero.

Run separate cancellation cases for:

- sponsor changes away from Colonial Resettlement;
- target ceases to be a primary-culture homeland;
- target owner changes externally;
- sponsor becomes invalid or hostile to the current target owner.

Each case must emit `EVALUATION_FAILED` or reach the owner-change cleanup, then emit `CANCELLED`. No project marker or versioned state variable may remain.

## Final-state evidence

An effect log proves only immediate execution. After completion or cancellation:

1. advance at least one monthly pulse;
2. save and reload;
3. inspect ownership, state type, project marker and country counters again;
4. search later log entries for another Mod rewriting the same state or top-level definition.

Only this post-reload observation counts as final retained-state evidence.

## AI and performance runs

Run a 24-month functional observer test, followed by a five-year stability test. Record starts, legal targets, completions, cancellations, native colonies and stuck projects. Then repeat the same save and speed with FFCS disabled for a tick-time baseline. The performance run must have `ffcs_debug_enabled_v1` removed.

Release thresholds are defined in `PERFORMANCE_AND_AI.md`.
