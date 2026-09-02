# Implementation Plan

## Milestone 1 — Contract and vertical slice

- create standalone metadata, dependencies, localization and validation tools;
- add the state-selecting diplomatic action;
- enforce the primary-culture-homeland trigger for player and AI;
- create versioned project variables, counters and monthly dispatch;
- complete a project by transferring the whole selected state as an initial executable fallback.

Acceptance: the action appears, invalid states cannot be selected, an AI proposal uses the same filter, progress survives a save/load and completion leaves an unincorporated state.

## Milestone 2 — Generated territorial growth

- parse Firefall's final state-region database;
- read province adjacency from `provinces.png`;
- generate deterministic contiguous four-phase province lists;
- dispatch the correct generated state-region effect at each threshold;
- retain whole-state completion as the safety fallback.

Acceptance: every generated province belongs to its state region, appears in exactly one phase, no phase contains the reserved final province, and running the generator twice produces identical bytes.

## Milestone 3 — Friction and feedback

- add resistance and progress modifiers;
- add setback, cancellation and completion notifications/events;
- reflect access, institution and technology in AI scores;
- add defensive cleanup when law, culture, target ownership or sponsor validity changes.

Acceptance: projects cannot become immortal, counters return to zero, and the AI does not start projects it cannot maintain.

## Milestone 4 — AI/native-path integration

- copy the final upstream strategic-region stance table;
- set native `stance_colonize_region` score to zero only for Colonial Resettlement;
- reduce native colonial-growth generation below zero for Colonial Resettlement so the engine rejects Establish Colony before seed creation;
- make company colonization charters unavailable to Colonial Resettlement owners;
- retain vanilla/Core behavior for Colonial Exploitation and Frontier Colonization;
- run hands-off tests for proposal rate, completion rate and invalid-target rate.

Acceptance: neither players, AI nor companies can open a native colony while using Colonial Resettlement; all custom targets are primary-culture homelands; and at least one eligible great/major power can complete projects without player intervention.

## Milestone 5 — Verification

- parse metadata;
- check localization BOM/key parity;
- check braces, quotes, duplicate owned IDs and generated manifest;
- inspect `error.log`, `game.log` and `debug.log` in a clean runtime test;
- verify the native Establish Colony command reports no colonial growth and creates no seed province under Colonial Resettlement;
- verify a Colonial Resettlement owner cannot grant a company colonization charter;
- test new game, old save, AI-only observer and law/culture change cleanup.

Static validation now supports an optional parameterized final-stack audit. It conservatively bounds all literal positive colonial-growth-generation sources, checks exact AI table parity after removing the one FFCS gate, and reports the final upstream law and charter providers. The detailed runtime procedure and diagnostic marker contract are maintained in `RUNTIME_TEST_MATRIX.md`.
