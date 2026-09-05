# FFPA Cultural Settlement System — Agent Guide

## Scope

This standalone Victoria 3 1.13 mod replaces the native player, AI and company-charter paths for Colonial Resettlement and Frontier Colonization with a custom, primary-culture-homeland-only settlement system. It is designed for the final database produced by:

1. `[1.13] Tech & Res`
2. `2050: The Fire Falls`
3. `2050 Firefall — Core Balance Adapter`
4. this mod

The identity and dependency contract in `.metadata/metadata.json` is authoritative.

## Ownership

This mod owns only:

- the `ffcs_*` diplomatic action, triggers, values, effects, modifiers, events, notifications and save variables;
- generated `ffcs_*` province-route triggers and state-region phase effects;
- the final `REPLACE` copies of Firefall's `law_colonial_resettlement` and `law_frontier_colonization`, changed only to place the native colonial-growth-generation hard-off inside each existing `modifier` block;
- the final `REPLACE:colonization_charter` copy needed to add both law guards to its singleton `possible` section;
- the final `INJECT:ai_strategy_default` copy needed to disable native AI colonization for both laws.

It does not semantically alter the rest of those copied law definitions, the colonial institution definition, global colony concurrency defines, state-region data, culture definitions, or native colonization GUI. The validator must keep both law copies token-identical to the final Firefall provider after removing the single FFCS hard-off field. Colonial Affairs levels remain the capacity input for FFCS, while the law-level hard-off makes the engine-native map command invalid before execution.

## Stable save interfaces

Do not rename or change the meaning of these without a versioned migration:

- `ffcs_active_settlement_count_v1`
- `ffcs_active_settlement_states_v1`
- `ffcs_inbound_settlement_count_v1`
- `ffcs_settlement_sponsor_v1`
- `ffcs_settlement_original_owner_v1`
- `ffcs_settlement_progress_v1`
- `ffcs_settlement_phase_v1`
- `ffcs_settlement_resistance_v1`
- `ffcs_settlement_schema_v1`
- `ffcs_settlement_route_v2`
- `ffcs_settlement_provinces_v2`

## Generated data

`common/scripted_effects/ffcs_generated_province_phases.txt` and `common/scripted_triggers/ffcs_generated_province_routes.txt` are generated from the Firefall state-region database and `provinces.png`. Keep them directly inside their database directories because Victoria 3 does not load these databases recursively. Modify the generator, not the generated files. Generated effects must use unquoted literal province database IDs because Victoria 3 1.13 has no proven dynamic province-list effect input. Generated seed triggers must receive sponsor and target-owner scopes explicitly and must not depend on the caller's `root` scope.

## Required checks

Before editing, inspect `git status --short --branch` where applicable and preserve user changes. Validate:

- JSON metadata parsing;
- balanced Paradox Script braces and quotes;
- unique owned top-level IDs;
- identical English and Simplified Chinese localization key sets;
- UTF-8 BOM on localization files;
- generated data determinism and complete province assignment;
- exact final Firefall token parity for both replaced laws after removing the FFCS hard-off field;
- the final upstream `ai_strategy_default` strategic-region score table;
- `git diff --check` where the directory is in a Git worktree.

Runtime evidence must distinguish file loading, top-level parsing, on-action dispatch, trigger/effect execution and final state after later-loaded content.

Do not commit, reset, clean, rebase or force-push unless explicitly requested.
