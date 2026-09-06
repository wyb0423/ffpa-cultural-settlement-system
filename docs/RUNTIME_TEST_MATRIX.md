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

Enabling diagnostics also runs a one-shot AI eligibility probe. Re-run it at
any time without toggling the switch:

```text
event ffcs_debug.3
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
FFCS|PROJECT_CREATED / FFCS|PROJECT_REJECTED
FFCS|AI_PROJECT_STARTED
FFCS|PROJECT_CARRIER_REBOUND
FFCS|PROJECT_RECOUNTED
FFCS|SEED_TRANSFERRED
FFCS|PHASE_APPLIED / FFCS|CLAIM_GRANTED
FFCS|TARGET_EXHAUSTED
FFCS|PROJECT_COMPLETED / FFCS|PROJECT_CANCELLED
FFCS|JOURNAL_INVALIDATED
FFCS|AI_BLOCKED / FFCS|AI_CANDIDATE_FOUND / FFCS|AI_NO_ELIGIBLE_TARGET
```

Every routine marker above is emitted only while `ffcs_debug_enabled_v1` exists, except `FFCS|AI_PROJECT_STARTED` and `FFCS|INVARIANT_FAILED`, which are unconditional. Sponsor, region and project fields must not be blank or `NULL_STATE`.

The AI probe logs only the first eligible state for each otherwise ready AI
sponsor. `AI_NO_ELIGIBLE_TARGET` means the shared eligibility trigger rejected
every state. After the next half-yearly country pulse, an eligible sponsor must
emit `AI_PROJECT_STARTED`; a candidate without that marker means the shared AI
dispatcher or startup revalidation failed.

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

The player positive control must have the required strategic-region interest. The AI positive control does not need that interest because FFCS disables its native colonization stance; all homeland, owner, route, malaria and cap gates still apply.

As a separate negative control, prepare an otherwise eligible homeland state owned by an unrecognized country. It must not be listed or selected by either the player or AI.

## Lifecycle and cleanup

For one valid project, confirm in order:

1. acceptance immediately transfers a visible foothold and emits `PROJECT_CREATED`, `SEED_TRANSFERRED`, `PROJECT_CARRIER_REBOUND` and `PHASE_APPLIED|...|PHASE=1` once; the rebound carrier may remain on the original owner's residual state or follow the sponsor when the whole state changes hands;
2. the first transferred land province touches sponsor territory, while an overseas project is directly adjacent across one sea node and transfers the port province first;
3. the sponsor emits one `PROJECT_RECOUNTED` on the monthly pulse, progress changes in the next save, never exceeds the next province threshold while a transfer is available, and no pulse transfers more than one later province;
4. crossing 50 emits `PHASE_APPLIED` and `CLAIM_GRANTED` once and gives the sponsor a claim on the state region without a milestone transfer burst;
5. every later transfer touches a province already recorded by this project and still sponsor-owned, and recalculates `ffcs_settlement_next_province_progress_v3`;
6. completion emits `PROJECT_COMPLETED`, leaves sponsor territory unincorporated unless already incorporated, prevents a new project from reaching 100 while another reachable transfer remains, and does not take disconnected islands or enclaves;
7. an overseas project deducts exactly `100000`, creates exactly a level 1 port after the foothold, and gives no refund on cancellation;
8. sponsor active and target inbound counters return to zero.

A selectable target state with only one remaining province must instead transfer and complete immediately on acceptance, including the normal overseas charge when applicable.

Run separate cancellation cases for:

- sponsor changes away from both FFCS laws;
- target ceases to be a primary-culture homeland;
- target owner changes externally;
- sponsor becomes invalid or hostile to the current target owner;
- the active land or overseas route is lost.

Losing only strategic-region interest must not cancel an active project. Also load a pre-0.3 active project without `ffcs_settlement_route_v2`; its next monthly check must cancel it, preserve transferred territory and recover both counters. A project from the quoted-province-ID or route-scope test build with phase progress but no sponsor-owned recorded province must clear the phantom frontier, re-evaluate the actual route and retry phase 1 on its next sponsor monthly pulse. An active project without `ffcs_settlement_next_province_progress_v3` must derive a threshold before its next monthly gain without resetting its current progress. A new large project must stop each gain at its next threshold, transfer exactly one reachable province and remain below 100 while another reachable transfer exists. A legacy project already at 100 must continue transferring one reachable province per pulse until it completes.

Each case must emit one `PROJECT_CANCELLED` with the expected reason. No project marker or versioned state variable may remain.

## Competitive settlement

1. Have countries A and B start projects in the same state region against the same decentralized country D. Both projects must establish distinct sponsor-owned carriers and appear only in their own sponsor's Journal Entry.
2. Have A attempt a second project in that region. It must fail revalidation with no fee, incident, counter or project variable mutation; B's project must not block A's first project.
3. Advance both projects across 50 progress. Both sponsors must receive a region claim exactly once.
4. Inspect every transferred province. Valid ownership transitions are D→A or D→B only; A→B and B→A are release blockers.
5. Let A take D's last reachable province. A must emit `PROJECT_COMPLETED`; B must emit `TARGET_EXHAUSTED` followed by one `PROJECT_CANCELLED|...|REASON=TARGET_EXHAUSTED` in the same ownership-change flow.
6. If B has no other project, its active counter must disappear and `JOURNAL_INVALIDATED` must follow. If B has another project elsewhere, only the exhausted row disappears.
7. Repeat with two different original owners in one state region. Exhausting one owner must not cancel projects against the other.
8. Repeat by removing D's last state through war or an external effect. The state-owner-change reconciliation must produce the same cleanup.
9. For an overseas contest over a unique port, confirm that a later sponsor without a remaining valid seed route cannot start and cannot take the first sponsor's port.
10. The acceptance tick must not emit `Failed to fetch variable for 'ffcs_transfer_budget_v2'`, `Event target link 'var' returned an unset scope` or `PROJECT_CARRIER_REBIND_FAILED`.

## Journal overview

1. Start one land project and one overseas project. Confirm a single **Cultural Settlements** Journal Entry appears with two rows.
2. Confirm each row shows the correct state, route, phase, progress and monthly capacity; clicking a row must open that state.
3. Advance one monthly pulse and confirm the actual progress change equals the smaller of the displayed monthly capacity and the distance to the next province threshold.
4. Cross 50, 75 and 95 progress and confirm the row phase and corresponding notification update once each, including when one pulse jumps directly to 100, with no extra province transfer caused solely by a milestone.
5. Complete or cancel one project and confirm only its row disappears. End the last project and confirm the Journal Entry invalidates, clears its saved row list and emits `JOURNAL_INVALIDATED` only while debug logging is enabled.
6. Load an old save with active projects but no `ffcs_active_settlement_states_v1` list. After one monthly pulse, confirm the list and Journal Entry rebuild without resetting project progress.
7. Load a pre-0.4 save containing the old state-region sponsor lock. The `ffcs_settlement_schema_v2` migration must preserve the project, remove the obsolete lock and allow another sponsor to compete in that region.
8. Load a save containing `ffcs_settlement_resistance_v1`. The `ffcs_settlement_schema_v3` migration must preserve project progress and remove the legacy resistance variable.

## Final-state evidence

An effect log proves only immediate execution. After completion or cancellation:

1. advance at least one monthly pulse;
2. save and reload;
3. inspect ownership, state type, project marker and country counters again;
4. search later log entries for another Mod rewriting the same state or top-level definition.

Only this post-reload observation counts as final retained-state evidence.

## AI and performance runs

Restart the game after installing the scripts, then run a 24-month functional observer test followed by a five-year stability test. The first eligible AI start should occur on the next half-yearly country pulse and emit unconditional `AI_PROJECT_STARTED`. Record starts, legal targets, completions, cancellations, native colonies and stuck projects. Then repeat the same save and speed with FFCS disabled for a tick-time baseline. The performance run must have `ffcs_debug_enabled_v1` removed.

Release thresholds are defined in `PERFORMANCE_AND_AI.md`.
