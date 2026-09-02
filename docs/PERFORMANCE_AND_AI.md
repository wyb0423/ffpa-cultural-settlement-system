# Performance and AI Assessment

## Static cost model

The hot path is the country monthly pulse:

1. one cheap `has_variable` gate per country;
2. only countries with inbound projects iterate their owned state scopes;
3. only marked states execute progress logic;
4. province transfer occurs at most four times per project lifetime.

If `C` is the number of countries, `T` the number of target countries with projects, `S_t` their owned states and `P` active projects, monthly work is approximately:

`O(C + sum(S_t) + P)`

It is not `O(C * world_states)` and does not scan pops, buildings or provinces monthly. The generated dispatch file is large on disk, but only one state-region branch is selected when a phase fires.

In the inspected Firefall start data there are roughly 801 referenced country tags and 670 province-bearing state regions. An inactive country performs only a variable-presence gate each month; schema variables are created only for countries that actually enter the system. With 20 active projects spread over small target countries, the extra monthly traversal should normally remain in the low hundreds of state checks, not hundreds of thousands.

Expected practical impact is low for ordinary project counts. Raising the per-country ceiling from 5 to 10 can at most double one sponsor's simultaneous marked states and phase-transfer bursts, but it does not change scheduler frequency or add a world scan. The generated four-phase script is about 0.76 MB for this map and the offline deterministic generation pass takes about 3 seconds on the development machine. The main runtime spike is not the dispatcher: it is ownership/market recalculation on the four transfer days per project.

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
- a target state reduced to its final province may be destroyed during completion before cleanup if effect ordering is wrong;
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
