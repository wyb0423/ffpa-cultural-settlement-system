# Performance and AI Assessment

## Static cost model

The hot path is the country monthly pulse:

1. one cheap `has_variable` gate per country;
2. only countries with inbound projects iterate their owned state scopes;
3. only marked states execute progress logic;
4. generated province scans occur only at the four phase thresholds and completion.

If `C` is the number of countries, `T` the number of target countries with projects, `S_t` their owned states and `P` active projects, monthly work is approximately:

`O(C + sum(S_t) + P)`

It is not `O(C * world_states)` and does not scan pops, buildings or provinces monthly. Route validity uses generated literal ownership checks, while frontier scans run only when a phase fires.

In the inspected Firefall start data there are roughly 801 referenced country tags and 670 province-bearing state regions. An inactive country performs only a variable-presence gate each month; schema variables are created only for countries that actually enter the system. With 20 active projects spread over small target countries, the extra monthly traversal should normally remain in the low hundreds of state checks, not hundreds of thousands.

Expected monthly impact remains low for ordinary project counts. Raising the per-country ceiling from 5 to 10 can at most double one sponsor's simultaneous marked states and phase-transfer bursts, but it does not add a monthly world scan. The generated effect and trigger files total about 59 MiB for this map and the offline deterministic generation pass takes about 2 seconds on the development machine. A frontier sweep is linear in state size per pass and can become quadratic for an unfavourable province-ID order; runtime profiling must cover both initial loading and large-state phase ticks.

## AI feasibility

The AI can operate the system because the diplomatic-action AI API provides the selected state in `will_propose_with_states` and `propose_score`. The AI does not need to click a custom button or reason about hidden variables after starting a project.

AI safety rules:

- evaluation chance only for eligible major/great powers or colonial countries;
- no proposal above the project cap;
- project cap is exactly two per Colonial Affairs institution level (2/4/6/8/10);
- no proposal while bankrupt/defaulting or in a dangerous war state;
- exact homeland and access checks before proposal;
- adjacency, claims, existing regional presence and strategic AI value increase score;
- remote projects receive a strong penalty;
- native colonization stance is disabled for this law so the AI does not split attention between systems;
- native Establish Colony is invalid because the law produces no colonial growth;
- company colonization charters are unavailable to owners using this law.

## Risks requiring runtime evidence

- diplomatic-action AI may evaluate state combinations less often than expected;
- transferring province chunks can invalidate or recreate state scopes differently from static inspection;
- province scopes stored in a variable list require explicit save/reload evidence on 1.13;
- saved sponsor and state-region scopes may not survive the final whole-state ownership merge as expected;
- later-loaded AI mods can restore native colonization scores;
- later-loaded law or institution mods can overcome/remove the colonial-growth hard-off;
- later-loaded company-charter definitions can remove the law gate;
- engine state recalculation cost may be higher in Firefall's enlarged map.

## Hands-off test matrix

Run at normal speed for at least 24 in-game months in observer mode and record:

| Metric | Target |
|---|---:|
| invalid custom targets | 0 |
| native colonies opened by Resettlement players, AI or companies | 0 |
| native Establish Colony rejection | command invalid before execution with no-colonial-growth reason |
| company colonization charter under Colonial Resettlement | unavailable |
| projects stuck after invalidation | 0 |
| negative active/inbound counters | 0 |
| max simultaneous projects at institution levels 1–5 | 2/4/6/8/10 |
| eligible AI project starts | at least 1 |
| started projects completing or cleanly cancelling | 100% |
| sustained monthly tick regression | under 2% in the same save and speed |

Performance claims remain estimates until this runtime matrix is completed on the user's actual load order.
