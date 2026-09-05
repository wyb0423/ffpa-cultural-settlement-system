# Runtime Test Matrix

## Purpose

Static validation proves file structure and final-database assumptions. It does not prove that the engine selected the final `REPLACE`, dispatched an on-action, accepted a scope transition or retained the final state after later-loaded content. Run this matrix with the authoritative load order:

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

- native colony port provision `yes`, cost `100000` and level `1`;
- a negative colonial-growth remainder after the conservative positive-source bound;
- exact final Firefall token parity for both replaced laws plus one hard-off field each;
- exact Core Balance AI token parity plus one shared two-law gate;
- the expected final upstream law and company-charter providers for both laws.

## Diagnostic switch

With the game in debug mode, enable lifecycle logging from the console through
the bundled hidden debug event:

```text
event ffcs_debug.1
```

Disable it immediately after the functional test:

```text
event ffcs_debug.2
```

`ffcs_debug_enabled_v1` is a test-only global switch, not a supported save interface. Enabled logging emits only for countries and states already carrying FFCS work. Search `game.log` and its rotated files for `FFCS|`.

The generic `effect ...` console command is not available in Victoria 3 1.13;
the event command is the supported test entry point for this Mod.

Expected lifecycle markers:

```text
FFCS|CANDIDATE_CREATED
FFCS|SCHEDULER_REACHED
FFCS|EVALUATION_PASSED / FFCS|EVALUATION_FAILED
FFCS|SEED_TRANSFERRED
FFCS|EFFECT_APPLIED / FFCS|CANCELLED
```

## Gate A — Native Establish Colony

### FFCS laws

1. Use a recognized country with Colonial Resettlement, Colonization technology and at least one Colonial Affairs level.
2. Select a state that would otherwise be colonizable.
3. Confirm that **Establish Colony** is invalid before execution with the no-colonial-growth reason.
4. Attempt the command and advance one day.
5. Confirm that no seed province, native colony marker or company colony was created.
6. Repeat steps 1–5 under Frontier Colonization.

### Control law

Repeat with Colonial Exploitation. Establish Colony must become valid when all ordinary requirements are met. This distinguishes the FFCS law gate from a global colonization failure.

## Gate B — Company colonization charter

1. Use a company eligible for `colonization_charter` under ordinary vanilla conditions.
2. Under Colonial Resettlement and then Frontier Colonization, confirm that the charter is unavailable and displays the FFCS law explanation.
3. Confirm that AI cannot grant it during an observer run.
4. Switch to a control colonization law and confirm that the original unrecognized-owner and company eligibility rules still apply.

## Gate C — Cultural target restriction

For the same sponsor, prepare two otherwise equivalent target states:

- positive: a decentralized-country state that is a homeland of at least one sponsor primary culture;
- negative: a decentralized-country state that is not a homeland of any sponsor primary culture.

The custom diplomatic action must list/select only the positive state. Repeat once for a player and once for AI. A negative state receiving a project is a release blocker even if it later cancels.

As a separate negative control, prepare an otherwise eligible homeland state owned by an unrecognized country. It must not be listed or selected by either the player or AI.

## Lifecycle and cleanup

For one valid project, confirm in order:

1. acceptance immediately transfers a visible foothold and emits `SEED_TRANSFERRED` then `CANDIDATE_CREATED` once;
2. the first transferred land province touches sponsor territory, while an overseas project is directly adjacent across one sea node and transfers the port province first;
3. the sponsor emits `SCHEDULER_REACHED` on the monthly pulse, and both progress and resistance change in the next save;
4. the state emits `EVALUATION_PASSED` and advances;
5. every later transfer touches a province already recorded by this project and still sponsor-owned;
6. completion emits `EFFECT_APPLIED`, leaves sponsor territory unincorporated unless already incorporated, and does not claim disconnected islands or enclaves;
7. an overseas project deducts exactly `100000`, creates exactly a level 1 port after the foothold, and gives no refund on cancellation;
8. sponsor active and target inbound counters return to zero.

A selectable target state with only one remaining province must instead transfer and complete immediately on acceptance, including the normal overseas charge when applicable.

Run separate cancellation cases for:

- sponsor changes away from both FFCS laws;
- target ceases to be a primary-culture homeland;
- target owner changes externally;
- sponsor becomes invalid or hostile to the current target owner;
- the active land or overseas route is lost.

Losing only strategic-region interest must not cancel an active project. Also load a pre-0.3 active project without `ffcs_settlement_route_v2`; its next monthly check must cancel it, preserve transferred territory and recover both counters. A project from the quoted-province-ID or route-scope test build with phase progress but no sponsor-owned recorded province must clear the phantom frontier, re-evaluate the actual route and retry phase 1 on its next sponsor monthly pulse.

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
