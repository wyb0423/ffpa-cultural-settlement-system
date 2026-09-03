# FFPA Cultural Settlement System — Agent Guide

## Scope

This standalone Victoria 3 1.13 mod replaces the native player, AI and company-charter paths for Colonial Resettlement with a custom, primary-culture-homeland-only settlement system. It is designed for the final database produced by:

1. `[1.13] Tech & Res`
2. `2050: The Fire Falls`
3. `2050 Firefall — Core Balance Adapter`
4. this mod

The identity and dependency contract in `.metadata/metadata.json` is authoritative.

## Ownership

This mod owns only:

- the `ffcs_*` diplomatic action, triggers, values, effects, modifiers, events, notifications and save variables;
- generated `ffcs_*` province-route triggers and state-region phase effects;
- the `INJECT:law_colonial_resettlement` native colonial-growth-generation hard-off guard;
- the `INJECT:colonization_charter` availability guard for Colonial Resettlement owners;
- the final `INJECT:ai_strategy_default` copy needed to disable native AI colonization for `law_colonial_resettlement`.

It does not own the rest of the law definition, the colonial institution definition, global colony concurrency defines, state-region data, culture definitions, or native colonization GUI. Colonial Affairs levels remain the capacity input for FFCS, while the law-level hard-off makes the engine-native map command invalid before execution.

## Stable save interfaces

Do not rename or change the meaning of these without a versioned migration:

- `ffcs_active_settlement_count_v1`
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

`common/scripted_effects/generated/ffcs_generated_province_phases.txt` and `common/scripted_triggers/generated/ffcs_generated_province_routes.txt` are generated from the Firefall state-region database and `provinces.png`. Modify the generator, not the generated files. Generated effects must use literal province IDs because Victoria 3 1.13 has no proven dynamic province-list effect input.

## Required checks

Before editing, inspect `git status --short --branch` where applicable and preserve user changes. Validate:

- JSON metadata parsing;
- balanced Paradox Script braces and quotes;
- unique owned top-level IDs;
- identical English and Simplified Chinese localization key sets;
- UTF-8 BOM on localization files;
- generated data determinism and complete province assignment;
- the final upstream `ai_strategy_default` strategic-region score table;
- `git diff --check` where the directory is in a Git worktree.

Runtime evidence must distinguish file loading, top-level parsing, on-action dispatch, trigger/effect execution and final state after later-loaded content.

Do not commit, reset, clean, rebase or force-push unless explicitly requested.
