# Cultural Settlement System — Design

## Goal

When a country uses `law_colonial_resettlement`, allow settlement only in state regions that are homelands of at least one of that country's primary cultures. The restriction is a hard trigger shared by players and AI, not a growth penalty or AI preference.

## Why a separate system

The native colonization map interaction exposes neither a scriptable state-target trigger nor an AI target-state score. A colony growth-speed penalty is evaluated only after the engine has created the seed province. Region stances are also too coarse because one strategic region can contain both valid and invalid states.

Victoria 3 1.13 diplomatic actions do expose:

- a required state picker (`state_selection = second_required`);
- a per-state hard trigger (`second_state_trigger`);
- a direct acceptance effect;
- state-aware AI proposal gates and scores.

The custom diplomatic action is therefore the authoritative entry point.

Victoria 3 1.13.11 exposes a stronger engine command gate: `ESTABLISH_COLONY_NO_COLONIAL_GROWTH` invalidates **Establish Colony** when the acting country produces no colonial growth. Colonial Resettlement therefore receives `state_colony_growth_creation_factor = -100`, a hard-off sentinel larger than every positive creation-factor source in the supported final database. This makes the command invalid before execution and prevents seed-province creation. The Colonial Affairs institution remains active so its investment level and bureaucracy cost continue to drive FFCS capacity and speed.

Company colonization charters are a separate engine-native seed-colony entry point. The final `colonization_charter` definition is injected with a law gate so neither players nor AI can grant one while the owner uses Colonial Resettlement. The native AI strategic-region stance is also disabled for this law to avoid wasted evaluation. Colonial Exploitation and Frontier Colonization are deliberately unaffected.

## Eligibility contract

A project may start only when all of the following are true:

- actor uses `law_colonial_resettlement`;
- actor is recognized and not decentralized;
- target is decentralized or unrecognized and is not a recognized overlord's subject;
- selected state is a primary-culture homeland of the actor;
- actor has a land-adjacent route or a coastal state plus a port;
- actor has the required strategic-region interest tier;
- selected state has no active `ffcs` project;
- actor is below its custom project cap of two projects per Colonial Affairs level;
- actor and target are not at war with each other.

The same trigger is repeated defensively when the monthly project executes. Culture changes therefore cancel an invalid project instead of allowing it to finish.

## State machine

```text
available state
    -> project started
    -> phase 0 / administrative preparation
    -> phase 1 / seed province
    -> phase 2 / contiguous expansion
    -> phase 3 / contiguous expansion
    -> phase 4 / contiguous expansion
    -> completion / remaining state transferred and set unincorporated

At any monthly tick:
    invalid sponsor, law, culture or ownership -> cancel and clean counters
    severe resistance roll -> setback or cancellation event
```

The project is stored on the target owner's residual state object. The sponsor and original owner keep numeric active/inbound counters. This avoids persistent lists containing destroyed state scopes.

`on_state_owner_change` cancels a project immediately if war or another effect transfers its residual target state. Cleanup decrements the saved original owner rather than the new owner, preventing stranded concurrency counters.

## Progress model

Monthly progress is calculated in integer points:

- base: 5;
- colonial affairs institution level: +2/+4/+6/+8/+10;
- quinine: +2;
- civilizing mission: +3;
- land adjacency: +3;
- active projects divide the final total, with a floor of 1;
- severe resistance can impose a temporary penalty.

Thresholds are 25, 50, 75 and 100. Each threshold transfers the next generated province phase. At 100 the remaining target state is transferred and set unincorporated.

The institution is read through proven 1–5 trigger tiers because Victoria 3 1.13 exposes an investment-level comparison trigger but no proven numeric getter. The same explicit tiers set the concurrent-project limits to 2/4/6/8/10. Lowering institution investment does not cancel projects already in progress, but it prevents starting another project until the active count falls below the new cap.

## Province phases

The generator reads the final Firefall state-region files and province map. For each land state region it:

1. chooses the port, otherwise city, otherwise first province as the seed;
2. builds an in-region adjacency graph from four-neighbour pixel contact;
3. orders provinces with breadth-first expansion from the seed;
4. divides that order into four approximately equal contiguous phases;
5. writes literal `set_owner_of_provinces` lists inside a generated state-region dispatch effect.

The final phase leaves at least one province with the original owner; completion uses `set_state_owner` for the remainder. A state with too few provinces falls back to fewer meaningful phases.

## Native feature parity

| Native behavior | Result | Notes |
|---|---|---|
| exact target eligibility | reproduced | hard state trigger for both player and AI |
| coastal/adjacent access | reproduced | same style of route gate as native claim action |
| initial foothold | reproduced | generated seed phase |
| province-by-province visual growth | approximated | four contiguous chunks, not engine-selected individual provinces |
| growth divided among colonies | reproduced in intent | custom active-project divisor |
| institution/technology scaling | approximated | explicit tiered progress model |
| malaria/terrain delay | approximated | scripted resistance/progress modifiers |
| competition | partial | different owners/partitions can be targeted; one project per target state object |
| colony tension/native uprising | approximated | custom resistance and incidents |
| colony pause/resume | omitted initially | cancellation is automatic; manual controls can be added later |
| colonial state flag | not scriptable | completed land is unincorporated, not a native colony object |
| native player map interaction | disabled for Colonial Resettlement | zero colonial-growth generation invalidates the command before seed creation |
| company colonization charter | disabled for Colonial Resettlement | charter availability has the same law gate for player and AI |

## Compatibility

The final AI score table is copied from `2050 Firefall — Core Balance Adapter` and changes only the `stance_colonize_region` eligibility for Colonial Resettlement. The law hard-off relies on the final sum of `state_colony_growth_creation_factor`, and the company-charter gate relies on the final `colonization_charter` definition. All three are intentionally load-order-sensitive and must be compared whenever an upstream law, institution, AI strategy or charter definition changes.

Old saves may already contain engine-native colonies or active company charters created before version 0.2. FFCS does not destructively transfer or delete that territory. Such colonies receive no new growth while their owner keeps Colonial Resettlement; only new settlement projects use FFCS.

No machine-specific game or Workshop path is stored in runtime files. Tool scripts accept paths as command-line arguments.
