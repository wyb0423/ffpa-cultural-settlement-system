# FFPA — Cultural Settlement System

This mod completely replaces engine-native colonization for countries using **Colonial Resettlement**. A settlement can only target a state region owned by a decentralized country that is a homeland of one of the acting country's primary cultures.

The player starts a project through the **Establish Cultural Settlement** diplomatic action and chooses the exact target state. AI countries use the same action and hard eligibility checks. Each Colonial Affairs institution level supports two concurrent projects, for a level 1–5 range of 2/4/6/8/10. Land projects start on a province sharing a real border with sponsor territory; overseas projects cost £100,000, start at the port province and create a level 1 port with the foothold. Later phases expand only from provinces already acquired by that project, so disconnected islands and enclaves require another project.

Colonial Resettlement receives a hard negative colonial-growth-generation sentinel. Victoria 3 rejects the native **Establish Colony** command when a country produces no colonial growth, before it creates the seed province. Company colonization charters are also unavailable under this law, and native AI colonization-region scoring remains disabled. Colonial Exploitation and Frontier Colonization retain their native behavior.

## Load order

1. `[1.13] Tech & Res`
2. `2050: The Fire Falls`
3. `2050 Firefall — Core Balance Adapter`
4. `FFPA — Cultural Settlement System`

## Important limitation

Victoria 3 does not expose the native colony object, colony tension, or its internal province-growth scheduler as general script effects. This mod reproduces the visible workflow with a scripted project and a generated literal province-adjacency database. The resulting territory is unincorporated, but it is not an engine-native colony while the custom project is running. Legacy native colonies already present in an old save are not deleted; they stop receiving growth while their owner uses Colonial Resettlement.

The final implementation and compatibility boundaries are documented in `docs/CULTURAL_SETTLEMENT_DESIGN.md` and `docs/PERFORMANCE_AND_AI.md`. Static and in-game verification steps are in `docs/RUNTIME_TEST_MATRIX.md`.
