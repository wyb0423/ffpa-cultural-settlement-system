# Cultural Settlement System — Design

## Goal

When a country uses `law_colonial_resettlement` or `law_frontier_colonization`, allow settlement only in state regions that are homelands of at least one of that country's primary cultures. The restriction is a hard trigger shared by players and AI, not a growth penalty or AI preference.

## Why a separate system

The native colonization map interaction exposes neither a scriptable state-target trigger nor an AI target-state score. A colony growth-speed penalty is evaluated only after the engine has created the seed province. Region stances are also too coarse because one strategic region can contain both valid and invalid states.

Victoria 3 1.13 diplomatic actions do expose:

- a required state picker (`state_selection = second_required`);
- a per-state hard trigger (`second_state_trigger`);
- a direct acceptance effect;
- state-aware AI proposal gates and scores.

The custom diplomatic action is therefore the authoritative entry point.

Victoria 3 1.13.11 exposes a stronger engine command gate: `ESTABLISH_COLONY_NO_COLONIAL_GROWTH` invalidates **Establish Colony** when the acting country produces no colonial growth. Colonial Resettlement and Frontier Colonization therefore receive `state_colony_growth_creation_factor = -100`, a hard-off sentinel larger than every positive creation-factor source in the supported final database. This makes the command invalid before execution and prevents seed-province creation. The Colonial Affairs institution remains active so its investment level and bureaucracy cost continue to drive FFCS capacity and speed.

Company colonization charters are a separate engine-native seed-colony entry point. Because the charter's `possible` section is a singleton that cannot be appended safely, the final `colonization_charter` definition is replaced with an otherwise identical copy containing the shared law gate, so neither players nor AI can grant one while the owner uses Colonial Resettlement or Frontier Colonization. The native AI strategic-region stance is also disabled for both laws to avoid wasted evaluation. Colonial Exploitation is deliberately unaffected.

## Eligibility contract

A project may start only when all of the following are true:

- actor uses `law_colonial_resettlement` or `law_frontier_colonization`;
- actor is recognized or unrecognized, but not decentralized;
- target is decentralized;
- selected state is a primary-culture homeland of the actor;
- actor has an actual province border with the target, or direct strategic adjacency across one sea node to a target-controlled port province;
- actor has the required strategic-region interest tier;
- selected state has no active `ffcs` project;
- actor is below its custom project cap of two projects per Colonial Affairs level;
- actor and target are not at war with each other.

The monthly project defensively rechecks sponsor validity, target type and ownership, culture, hostility and access. Strategic-region interest is a start-only requirement and does not cancel an active project if it is later lost.

## State machine

```text
available state
    -> project started
    -> phase 0 / administrative preparation
    -> phase 1 / seed province
    -> phase 2 / contiguous expansion
    -> phase 3 / contiguous expansion
    -> phase 4 / contiguous expansion
    -> completion / final reachable province transferred

At any monthly tick:
    invalid sponsor, law, culture or ownership -> cancel and clean counters
    severe resistance roll -> setback or cancellation event
```

The project is stored on the target owner's residual state object. The sponsor and original owner keep numeric active/inbound counters. Monthly maintenance is dispatched from the sponsor's country pulse and scans only while that sponsor has active projects; this avoids relying on decentralized target countries receiving country pulses and avoids persistent lists containing destroyed state scopes.

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

Acceptance initializes progress at 25 and immediately applies phase 1, so every successful action produces a visible foothold. Later province-phase thresholds are 50, 75 and 95. At 100 only a final province still connected to this project's frontier is transferred; disconnected territory remains with the original owner.

The institution is read through proven 1–5 trigger tiers because Victoria 3 1.13 exposes an investment-level comparison trigger but no proven numeric getter. The same explicit tiers set the concurrent-project limits to 2/4/6/8/10. Lowering institution investment does not cancel projects already in progress, but it prevents starting another project until the active count falls below the new cap.

## Province phases

The generator reads the final Firefall state-region files and province map, builds four-neighbour pixel adjacency with horizontal map wrapping, and emits literal dispatchers. A land seed must be owned by the explicitly supplied target owner and touch a sponsor-owned province. An overseas seed requires direct strategic adjacency across one sea node and is the state region's target-owned port province. Passing the target owner explicitly is required because diplomatic-action state selection and acceptance do not share the same `root` scope. Each later candidate must be owned by the original target and touch a province recorded in this project's `ffcs_settlement_provinces_v2` list that is still sponsor-owned. Generated `set_owner_of_provinces` lists use unquoted province database IDs, matching the Victoria 3 1.13 effect syntax.

At acceptance/50/75/95 progress the remaining state is divided across 4/3/2/1 phases with ceiling rounding. Scans stop at the phase budget, a missing frontier, or one residual province. A selectable state already reduced to one province completes immediately at acceptance; otherwise completion claims that last province only if it remains on the same project frontier. Overseas projects charge `100000` when accepted and create a level 1 port during the immediate foothold transfer.

## Native feature parity

| Native behavior | Result | Notes |
|---|---|---|
| exact target eligibility | reproduced | hard state trigger for both player and AI |
| coastal/adjacent access | reproduced | actual province border or one-sea-node strategic adjacency to a target-controlled port province |
| initial foothold | reproduced | land-border seed or port seed transferred on acceptance |
| province-by-province visual growth | approximated | contiguous project-frontier chunks at four thresholds |
| overseas port cost and provision | reproduced | £100,000 at acceptance; level 1 port after foothold |
| growth divided among colonies | reproduced in intent | custom active-project divisor |
| institution/technology scaling | approximated | explicit tiered progress model |
| malaria/terrain delay | approximated | scripted resistance/progress modifiers |
| competition | partial | different owners/partitions can be targeted; one project per target state object |
| colony tension/native uprising | approximated | custom resistance and incidents |
| colony pause/resume | omitted initially | cancellation is automatic; manual controls can be added later |
| colonial state flag | not scriptable | completed land is unincorporated, not a native colony object |
| native player map interaction | disabled for both FFCS laws | zero colonial-growth generation invalidates the command before seed creation |
| company colonization charter | disabled for both FFCS laws | charter availability has the same law gate for player and AI |

## Compatibility

The final AI score table is copied from `2050 Firefall — Core Balance Adapter` and changes only the `stance_colonize_region` eligibility for the two FFCS laws. Both final Firefall law definitions are copied with only one added `state_colony_growth_creation_factor = -100` field inside their existing `modifier` blocks; this avoids relying on duplicate singleton-block injection. The company-charter gate relies on the final `colonization_charter` definition. All three are intentionally load-order-sensitive and must be compared whenever an upstream law, institution, AI strategy or charter definition changes.

Old saves may already contain engine-native colonies or active company charters created before version 0.2. FFCS does not destructively transfer or delete that territory. Active FFCS projects created before version 0.3 lack a provable route/frontier record and cancel on their next monthly check without returning land or money. Projects from the broken quoted-province-ID or route-scope test builds reset a phase that left no sponsor-owned frontier, re-evaluate the real land/port seed and retry it on the next sponsor monthly pulse. Only new projects use the v2 route and province-list interfaces.

No machine-specific game or Workshop path is stored in runtime files. Tool scripts accept paths as command-line arguments.
