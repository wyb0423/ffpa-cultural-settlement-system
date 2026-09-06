# Performance and AI Assessment

## Static cost model

The hot path is the country monthly pulse:

1. one cheap `has_variable` gate per country;
2. only countries with inbound projects iterate their owned state scopes;
3. only marked states execute progress logic;
4. generated province scans occur only when a project reaches its next province-transfer threshold or completion.

If `C` is the number of countries, `T` the number of target countries with projects, `S_t` their owned states and `P` active projects, monthly work is approximately:

`O(C + sum(S_t) + P)`

It is not `O(C * world_states)` and does not scan pops, buildings or provinces monthly. Route validity uses generated literal ownership checks, while frontier scans run only when a phase fires.

In the inspected Firefall start data there are roughly 801 referenced country tags and 675 province-bearing state regions. An inactive country performs only a variable-presence gate each month; schema variables are created only for countries that actually enter the system. With 20 active projects spread over small target countries, the extra monthly traversal should normally remain in the low hundreds of state checks, not hundreds of thousands.

Expected monthly impact remains low for ordinary project counts. Raising the per-country ceiling from 5 to 10 can at most double one sponsor's simultaneous marked states and province-transfer checks, but it does not add a monthly world scan. The generated effect and trigger files total about 88 MiB for this map and the offline deterministic generation pass takes about 3 seconds on the development machine. Each transfer uses an equal-weight `random_list` whose candidate checks are linear in the current state-region size; runtime profiling must cover both initial loading and large-state transfer ticks.

## AI feasibility

The diplomatic-action AI path is disabled. A native half-yearly country pulse selects one legal target state for each eligible AI sponsor below its project cap, then calls the same startup effect as the player action. This avoids depending on the engine's opaque diplomatic-action proposal scheduling.

AI safety rules:

- each eligible AI country can start at most one project per half-yearly pulse;
- no start above the project cap;
- project cap is exactly two per Colonial Affairs institution level (2/4/6/8/10);
- no start while bankrupt/defaulting or at war;
- exact homeland and access checks before proposal;
- the player strategic-interest gate is waived only for AI because the native colonization stance that normally supplies it is disabled;
- one state is chosen randomly from the complete eligible set;
- native colonization stance is disabled for this law so the AI does not split attention between systems;
- native Establish Colony is invalid because the law produces no colonial growth;
- company colonization charters are unavailable to owners using this law.

## Risks requiring runtime evidence

- the half-yearly global eligible-state selection cost may be higher than static inspection suggests;
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
| native colonies opened by players, AI or companies under either FFCS law | 0 |
| native Establish Colony rejection | command invalid before execution with no-colonial-growth reason |
| company colonization charter under either FFCS law | unavailable |
| projects stuck after invalidation | 0 |
| negative active/inbound counters | 0 |
| max simultaneous projects at institution levels 1–5 | 2/4/6/8/10 |
| eligible AI project starts | at least 1 |
| started projects completing or cleanly cancelling | 100% |
| sustained monthly tick regression | under 2% in the same save and speed |

Performance claims remain estimates until this runtime matrix is completed on the user's actual load order.
