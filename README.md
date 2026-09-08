# FFPA — Cultural Settlement System

This mod completely replaces engine-native colonization for countries using **Colonial Resettlement** or **Frontier Colonization**. A settlement can only target a state region owned by a decentralized country that is a homeland of one of the acting country's primary cultures.

The player starts a project through the **Establish Homeland Settlement** diplomatic action and chooses the exact target state. Acceptance immediately establishes the first visible foothold. AI countries use a half-yearly dispatcher with the same hard eligibility checks and shared startup effect. Each Colonial Affairs institution level supports two concurrent projects, for a level 1–5 range of 2/4/6/8/10. Different countries may compete in the same state region, but one sponsor cannot run two projects there. Land projects start on a province sharing a real border with sponsor territory; overseas projects must be directly adjacent across one sea node, cost £100,000, start at the port province and create a level 1 port with the foothold. Later monthly progress transfers up to two provinces from the project's fixed original target when that month's progress pays each recalculated threshold; every transfer remains adjacent to land already acquired by that project, so competitors cannot transfer each other's settlement provinces.

While projects are active, the **Homeland Settlements** Journal Entry lists every project state with its route, phase, progress bar and monthly capacity. At 50 progress the sponsor gains a claim on the state region; expansion milestones at 50, 75 and 95 also generate notifications. Each monthly gain can pay at most two sequential province thresholds, recalculating after each transfer, so new projects cannot reach 100 while another reachable transfer remains. If competitors exhaust the original target's remaining land, losing projects terminate immediately and their sponsor's last Journal Entry closes.

Both laws receive a hard negative colonial-growth-generation sentinel. Victoria 3 rejects the native **Establish Colony** command when a country produces no colonial growth, before it creates the seed province. Company colonization charters are also unavailable under either law, and native AI colonization-region scoring remains disabled. Colonial Exploitation retains its native behavior.

## Load order

1. `[1.13] Tech & Res`
2. `2050: The Fire Falls`
3. `2050 Firefall — Core Balance Adapter`
4. `FFPA — Cultural Settlement System`

## Important limitation

Victoria 3 does not expose the native colony object, colony tension, or its internal province-growth scheduler as general script effects. This mod reproduces the visible workflow with a scripted project and a generated literal province-adjacency database. The resulting territory is unincorporated, but it is not an engine-native colony while the custom project is running. Legacy native colonies already present in an old save are not deleted; they stop receiving growth while their owner uses either FFCS law.

The final implementation and compatibility boundaries are documented in `docs/CULTURAL_SETTLEMENT_DESIGN.md` and `docs/PERFORMANCE_AND_AI.md`. Static and in-game verification steps are in `docs/RUNTIME_TEST_MATRIX.md`.
