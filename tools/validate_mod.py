#!/usr/bin/env python3
"""Static validation for FFPA Cultural Settlement System."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path


LOCALIZATION_KEY = re.compile(r"^\s*([A-Za-z0-9_.-]+):(?:\d+)?\s+", re.MULTILINE)
TOP_LEVEL_KEY = re.compile(r"^\s*([A-Za-z0-9_.:-]+)\s*=\s*\{")
COLONY_CREATION_FACTOR = re.compile(
    r"\bstate_colony_growth_creation_factor\s*=\s*"
    r"([-+]?\d+(?:\.\d+)?)\b"
)
COLONY_PORT_DEFINES = {
    "ESTABLISH_COLONY_PROVIDE_PORT": "yes",
    "ESTABLISH_COLONY_PORT_COST": "100000",
    "ESTABLISH_COLONY_PORT_LEVEL": "1",
}


@dataclass(frozen=True)
class StackRoot:
    label: str
    path: Path


def script_balance(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8-sig")
    depth = 0
    in_string = False
    escaped = False
    line = 1
    errors: list[str] = []
    index = 0
    while index < len(text):
        char = text[index]
        if char == "\n":
            line += 1
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            index += 1
            continue
        if char == "#":
            next_newline = text.find("\n", index)
            if next_newline < 0:
                break
            index = next_newline
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth < 0:
                errors.append(f"{path}: unexpected closing brace at line {line}")
                depth = 0
        index += 1
    if in_string:
        errors.append(f"{path}: unterminated string")
    if depth:
        errors.append(f"{path}: brace balance is {depth}")
    return errors


def top_level_keys(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8-sig")
    keys: list[str] = []
    depth = 0
    in_string = False
    escaped = False
    for raw_line in text.splitlines():
        line = raw_line
        visible: list[str] = []
        index = 0
        while index < len(line):
            char = line[index]
            if in_string:
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == '"':
                    in_string = False
                visible.append(" ")
            elif char == '"':
                in_string = True
                visible.append(" ")
            elif char == "#":
                break
            else:
                visible.append(char)
            index += 1
        code = "".join(visible)
        if depth == 0:
            match = TOP_LEVEL_KEY.match(code)
            if match:
                keys.append(match.group(1))
        depth += code.count("{") - code.count("}")
    return keys


def localization_keys(path: Path) -> tuple[list[str], bool]:
    data = path.read_bytes()
    text = data.decode("utf-8-sig")
    keys = [
        key
        for key in LOCALIZATION_KEY.findall(text)
        if key not in {"l_english", "l_simp_chinese"}
    ]
    return keys, data.startswith(b"\xef\xbb\xbf")


def strip_script_comments(text: str) -> str:
    """Remove Paradox comments without treating # inside strings as a comment."""
    output: list[str] = []
    in_string = False
    escaped = False
    index = 0
    while index < len(text):
        char = text[index]
        if in_string:
            output.append(char)
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            index += 1
            continue
        if char == '"':
            in_string = True
            output.append(char)
            index += 1
            continue
        if char == "#":
            while index < len(text) and text[index] not in "\r\n":
                index += 1
            continue
        output.append(char)
        index += 1
    return "".join(output)


def script_tokens(text: str) -> list[str]:
    visible = strip_script_comments(text)
    return re.findall(
        r'"(?:\\.|[^"\\])*"|>=|<=|!=|\?=|==|[{}=<>]|[^\s{}=<>]+',
        visible,
    )


def find_token_sequence(tokens: list[str], sequence: list[str]) -> list[int]:
    if not sequence:
        return []
    return [
        index
        for index in range(len(tokens) - len(sequence) + 1)
        if tokens[index : index + len(sequence)] == sequence
    ]


def definition_tokens(path: Path, key: str) -> list[str]:
    tokens = script_tokens(path.read_text(encoding="utf-8-sig"))
    names = {key, f"REPLACE:{key}"}
    for index in range(len(tokens) - 2):
        if tokens[index] not in names or tokens[index + 1 : index + 3] != ["=", "{"]:
            continue
        depth = 0
        for end in range(index + 2, len(tokens)):
            if tokens[end] == "{":
                depth += 1
            elif tokens[end] == "}":
                depth -= 1
                if depth == 0:
                    return tokens[index : end + 1]
    raise ValueError(f"definition {key} not found in {path}")


def files_containing(directory: Path, *needles: str) -> list[Path]:
    if not directory.is_dir():
        return []
    matches: list[Path] = []
    for path in sorted(directory.rglob("*.txt")):
        text = path.read_text(encoding="utf-8-sig")
        if all(needle in text for needle in needles):
            matches.append(path)
    return matches


def final_definition_provider(
    stack_roots: list[StackRoot], database: str, key: str
) -> tuple[str, Path] | None:
    provider: tuple[str, Path] | None = None
    definition = re.compile(
        rf"^\s*(?:(REPLACE|INJECT):)?{re.escape(key)}\s*=\s*\{{",
        re.MULTILINE,
    )
    for stack_root in stack_roots:
        directory = stack_root.path / "common" / database
        if not directory.is_dir():
            continue
        for path in sorted(directory.rglob("*.txt")):
            text = strip_script_comments(path.read_text(encoding="utf-8-sig"))
            for match in definition.finditer(text):
                if match.group(1) != "INJECT":
                    provider = (stack_root.label, path)
    return provider


def validate_final_stack(
    stack_roots: list[StackRoot], root: Path, hard_off: float
) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    report: list[str] = []

    for stack_root in stack_roots:
        if not (stack_root.path / "common").is_dir():
            errors.append(
                f"{stack_root.label} root has no common directory: {stack_root.path}"
            )
    if errors:
        return errors, report

    for define, expected in COLONY_PORT_DEFINES.items():
        matches: list[tuple[str, Path, str]] = []
        pattern = re.compile(rf"^\s*{define}\s*=\s*([^\s#]+)", re.MULTILINE)
        for stack_root in stack_roots:
            directory = stack_root.path / "common" / "defines"
            if not directory.is_dir():
                continue
            for path in sorted(directory.rglob("*.txt")):
                for match in pattern.finditer(path.read_text(encoding="utf-8-sig")):
                    matches.append((stack_root.label, path, match.group(1)))
        if not matches:
            errors.append(f"final stack does not define {define}")
            continue
        label, path, actual = matches[-1]
        if actual != expected:
            errors.append(
                f"{define} must remain {expected}, final value is {actual} from "
                f"{label}:{path.relative_to(stack_roots[[r.label for r in stack_roots].index(label)].path)}"
            )
        else:
            report.append(f"{define}: {actual}")

    # This deliberately overestimates the supported stack: duplicate definitions
    # from earlier layers are still counted, and every institution modifier is
    # multiplied by the maximum supported investment level of five.
    positive_bound = 0.0
    positive_sources: list[tuple[str, Path, int, float, int]] = []
    for stack_root in stack_roots:
        common_root = stack_root.path / "common"
        for path in sorted(common_root.rglob("*.txt")):
            relative = path.relative_to(common_root)
            if relative.parts[0] == "modifier_type_definitions":
                continue
            text = strip_script_comments(path.read_text(encoding="utf-8-sig"))
            for line_number, line in enumerate(text.splitlines(), start=1):
                if "state_colony_growth_creation_factor" not in line:
                    continue
                match = COLONY_CREATION_FACTOR.search(line)
                if not match:
                    errors.append(
                        "unbounded non-literal colonial growth source: "
                        f"{stack_root.label}:{relative}:{line_number}"
                    )
                    continue
                value = float(match.group(1))
                if value <= 0:
                    continue
                multiplier = 5 if relative.parts[0] == "institutions" else 1
                positive_bound += value * multiplier
                positive_sources.append(
                    (stack_root.label, relative, line_number, value, multiplier)
                )

    if hard_off + positive_bound >= 0:
        errors.append(
            "colonial growth hard-off is not stronger than the conservative "
            f"positive-source bound: {hard_off:g} + {positive_bound:g} >= 0"
        )
    report.append(
        "colonial growth bound: "
        f"hard-off {hard_off:g}, positive upper bound {positive_bound:g}, "
        f"remaining {hard_off + positive_bound:g}, "
        f"sources {len(positive_sources)}"
    )

    ai_baseline_matches = files_containing(
        stack_roots[-1].path / "common" / "ai_strategies",
        "INJECT:ai_strategy_default",
        "strategic_region_stance_type_scores",
    )
    if len(ai_baseline_matches) != 1:
        errors.append(
            "expected exactly one final Core Balance ai_strategy_default region "
            f"score table, found {len(ai_baseline_matches)}"
        )
    else:
        target_ai = (
            root
            / "common"
            / "ai_strategies"
            / "zzzzz_ffcs_disable_native_resettlement.txt"
        )
        baseline_tokens = script_tokens(
            ai_baseline_matches[0].read_text(encoding="utf-8-sig")
        )
        target_tokens = script_tokens(target_ai.read_text(encoding="utf-8-sig"))
        gate_tokens = script_tokens(
            "NOT = { ffcs_uses_cultural_settlement_law = yes }"
        )
        gate_positions = find_token_sequence(target_tokens, gate_tokens)
        if len(gate_positions) != 1:
            errors.append(
                "FFCS AI table must contain exactly one cultural-settlement law gate"
            )
        else:
            gate_index = gate_positions[0]
            del target_tokens[gate_index : gate_index + len(gate_tokens)]
            if target_tokens != baseline_tokens:
                mismatch = next(
                    (
                        index
                        for index, (target, baseline) in enumerate(
                            zip(target_tokens, baseline_tokens)
                        )
                        if target != baseline
                    ),
                    min(len(target_tokens), len(baseline_tokens)),
                )
                errors.append(
                    "FFCS AI table differs from the final Core Balance table "
                    f"beyond the expected law gate near token {mismatch}"
                )
            else:
                report.append(
                    "AI table: exact Core Balance token parity plus one two-law gate"
                )

    target_laws = (
        root / "common" / "laws" / "zzzzz_ffcs_colonial_resettlement_guard.txt"
    )
    hard_off_tokens = script_tokens("state_colony_growth_creation_factor = -100")
    for law in ("law_colonial_resettlement", "law_frontier_colonization"):
        law_provider = final_definition_provider(stack_roots, "laws", law)
        if law_provider is None:
            errors.append(f"final upstream {law} provider not found")
        else:
            label, path = law_provider
            baseline_tokens = definition_tokens(path, law)
            target_tokens = definition_tokens(target_laws, law)
            hard_off_positions = find_token_sequence(target_tokens, hard_off_tokens)
            if len(hard_off_positions) != 1:
                errors.append(f"FFCS {law} must contain exactly one hard-off modifier")
            else:
                hard_off_index = hard_off_positions[0]
                del target_tokens[
                    hard_off_index : hard_off_index + len(hard_off_tokens)
                ]
                if target_tokens != baseline_tokens:
                    errors.append(
                        f"FFCS {law} differs from its final upstream definition "
                        "beyond the expected hard-off modifier"
                    )
                else:
                    report.append(
                        f"{law}: exact final-upstream token parity plus hard-off"
                    )
            report.append(
                f"{law} provider: {label}:"
                f"{path.relative_to(stack_roots[[r.label for r in stack_roots].index(label)].path)}"
            )

    charter_provider = final_definition_provider(
        stack_roots, "company_charter_types", "colonization_charter"
    )
    if charter_provider is None:
        errors.append("final upstream colonization_charter provider not found")
    else:
        label, path = charter_provider
        report.append(
            f"charter provider: {label}:{path.relative_to(stack_roots[[r.label for r in stack_roots].index(label)].path)}"
        )

    return errors, report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fix-localization-bom", action="store_true")
    parser.add_argument("--game-root", type=Path)
    parser.add_argument("--tech-res-root", type=Path)
    parser.add_argument("--firefall-root", type=Path)
    parser.add_argument("--core-balance-root", type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    errors: list[str] = []

    metadata = root / ".metadata" / "metadata.json"
    try:
        parsed = json.loads(metadata.read_text(encoding="utf-8"))
        if parsed.get("id") != "com.wyb.ffpa-cultural-settlement-system":
            errors.append("metadata id is not the stable mod id")
        if parsed.get("supported_game_version") != "1.13.*":
            errors.append("supported game version is not 1.13.*")
        if parsed.get("version") != "0.3.0":
            errors.append("metadata version must be 0.3.0")
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"metadata parse failed: {exc}")

    common_files = sorted((root / "common").rglob("*.txt"))
    script_files = (
        common_files
        + sorted((root / "events").rglob("*.txt"))
        + sorted((root / "gui").rglob("*.gui"))
    )
    for path in script_files:
        errors.extend(script_balance(path))

    cap_trigger = (
        root / "common" / "scripted_triggers" / "ffcs_settlement_triggers.txt"
    ).read_text(encoding="utf-8-sig")
    cap_values = re.findall(
        r"var:ffcs_active_settlement_count_v1\s*<\s*(\d+)", cap_trigger
    )
    if cap_values != ["2", "4", "6", "8", "10"]:
        errors.append(
            "settlement cap must be 2/4/6/8/10 by Colonial Affairs level"
        )
    cultural_law_trigger = script_tokens(
        "ffcs_uses_cultural_settlement_law = { OR = { "
        "has_law_or_variant = law_type:law_colonial_resettlement "
        "has_law_or_variant = law_type:law_frontier_colonization } }"
    )
    if len(find_token_sequence(script_tokens(cap_trigger), cultural_law_trigger)) != 1:
        errors.append("cultural-settlement law trigger must contain both owned laws")

    diplomatic_action = (
        root / "common" / "diplomatic_actions" / "ffcs_cultural_settlement.txt"
    ).read_text(encoding="utf-8-sig")
    diplomatic_action_tokens = script_tokens(diplomatic_action)
    sponsor_type_gate = script_tokens(
        "OR = { is_country_type = recognized is_country_type = unrecognized }"
    )
    if not find_token_sequence(diplomatic_action_tokens, sponsor_type_gate):
        errors.append("settlement sponsors must be recognized or unrecognized countries")
    if not find_token_sequence(
        diplomatic_action_tokens,
        script_tokens("scope:target_country = { is_country_type = decentralized }"),
    ):
        errors.append("cultural settlements must target only decentralized countries")
    if not find_token_sequence(
        diplomatic_action_tokens,
        script_tokens(
            "custom_tooltip = { text = FFCS_REQUIRES_CULTURAL_SETTLEMENT_LAW_TT "
            "ffcs_uses_cultural_settlement_law = yes }"
        ),
    ):
        errors.append("both cultural-settlement laws must be a visible possible-condition")
    if diplomatic_action.count("ffcs_uses_cultural_settlement_law = yes") != 2:
        errors.append("player and diplomatic-action AI must share the two-law gate")
    action_icon = (
        root
        / "gfx"
        / "interface"
        / "icons"
        / "lens_toolbar_icons"
        / "da_ffcs_establish_cultural_settlement.dds"
    )
    if not action_icon.is_file():
        errors.append("cultural settlement diplomatic-action icon is missing")
    if diplomatic_action.count("add_treasury = -100000") != 1:
        errors.append("overseas settlement must charge exactly 100000 once")
    if "add_treasury = -5000" in diplomatic_action:
        errors.append("land settlements must not retain the old 5000 charge")
    if not find_token_sequence(
        diplomatic_action_tokens,
        script_tokens(
            "evaluation_chance = { value = 0 if = { limit = { "
            "ffcs_uses_cultural_settlement_law = yes "
            "has_technology_researched = colonization in_default = no "
            "is_at_war = no ffcs_below_settlement_cap = yes } add = 0.05 "
            "if = { limit = { country_rank = rank_value:great_power } add = 0.05 }"
        ),
    ):
        errors.append("eligible minor AI countries must receive a nonzero settlement evaluation chance")
    for required in (
        "show_effect_in_tooltip = no",
        "ffcs_generated_has_land_seed_v2 = { COUNTRY = scope:ffcs_settlement_sponsor TARGET = scope:ffcs_settlement_original_owner }",
        "ffcs_state_is_eligible_for_settlement = { COUNTRY = scope:country TARGET = scope:target_country STATE = root REGION = root.region }",
        "ffcs_state_is_eligible_for_settlement = { COUNTRY = root TARGET = scope:target_country STATE = scope:second_state REGION = scope:second_state.region }",
        "else_if = { limit = { ffcs_generated_has_port_seed_v2 = { TARGET = scope:ffcs_settlement_original_owner } } set_variable = { name = ffcs_settlement_route_v2 value = 2 } }",
        "set_variable = { name = ffcs_settlement_route_v2 value = 1 }",
        "set_variable = { name = ffcs_settlement_route_v2 value = 2 }",
        "limit = { var:ffcs_settlement_route_v2 = 2 } scope:ffcs_settlement_sponsor = { add_treasury = -100000 }",
    ):
        if not find_token_sequence(diplomatic_action_tokens, script_tokens(required)):
            errors.append(f"route selection or overseas charge missing: {required}")
    for required in (
        "limit = { exists = scope:second_state } save_temporary_scope_as = ffcs_settlement_sponsor",
        "scope:target_country = { save_temporary_scope_as = ffcs_settlement_original_owner ffcs_initialize_country_schema_v1 = yes }",
        "save_temporary_scope_as = ffcs_settlement_project",
        "state_region = { save_temporary_scope_as = ffcs_settlement_state_region set_variable = { name = ffcs_settlement_sponsor_v1 value = scope:ffcs_settlement_sponsor } }",
        "set_variable = { name = ffcs_settlement_sponsor_v1 value = scope:ffcs_settlement_sponsor }",
        "set_variable = { name = ffcs_settlement_original_owner_v1 value = scope:ffcs_settlement_original_owner }",
        "scope:ffcs_settlement_project = { set_variable = ffcs_internal_transfer_guard_v1 }",
        "ffcs_apply_settlement_phase_v2 = { DIVISOR = 4 }",
        "if = { limit = { scope:ffcs_settlement_project = { has_variable_list = ffcs_settlement_provinces_v2 } } scope:ffcs_settlement_project = { set_variable = { name = ffcs_settlement_progress_v1 value = 25 } set_variable = { name = ffcs_settlement_phase_v1 value = 1 } } }",
        "limit = { num_provinces = 1 } set_variable = { name = ffcs_settlement_progress_v1 value = 100 } ffcs_complete_settlement_project_v1 = yes",
        "add_to_variable_list = { name = ffcs_active_settlement_states_v1 target = scope:ffcs_settlement_project }",
        "add_journal_entry = { type = je_ffcs_cultural_settlement_overview }",
    ):
        if not find_token_sequence(diplomatic_action_tokens, script_tokens(required)):
            errors.append(f"accepted settlements must create an immediate foothold: {required}")
    if re.search(
        r"name\s*=\s*ffcs_settlement_(?:sponsor|original_owner)_v1\s+"
        r"value\s*=\s*(?:root|owner)\b",
        diplomatic_action,
    ):
        errors.append("settlement scope variables must be initialized from explicit saved scopes")

    trigger_tokens = script_tokens(cap_trigger)
    if not find_token_sequence(
        trigger_tokens,
        script_tokens("owner = { is_country_type = decentralized"),
    ) or not find_token_sequence(
        trigger_tokens,
        script_tokens("$TARGET$ = { is_country_type = decentralized }"),
    ):
        errors.append("settlement entry and monthly validity must require a decentralized target")
    if not find_token_sequence(
        trigger_tokens,
        script_tokens(
            "state_region = { OR = { has_variable = ffcs_settlement_sponsor_v1 any_scope_state = { has_variable = ffcs_settlement_sponsor_v1 } } }"
        ),
    ):
        errors.append("settlement entry must lock the entire state region while a project exists")
    for required in (
        "has_variable = ffcs_settlement_route_v2",
        "var:ffcs_settlement_route_v2 = 1",
        "var:ffcs_settlement_route_v2 = 2",
        "ffcs_generated_has_land_seed_v2 = {",
        "ffcs_generated_has_port_seed_v2 = {",
        "COUNTRY = $COUNTRY$",
        "TARGET = $TARGET$",
        "ffcs_generated_country_owns_port_v2 = {",
        "has_variable_list = ffcs_settlement_provinces_v2",
        "has_building = building_port",
        "$COUNTRY$ = { has_port_country = yes }",
        "is_homeland_of_country_cultures = $COUNTRY$",
    ):
        if not find_token_sequence(trigger_tokens, script_tokens(required)):
            errors.append(f"monthly settlement validity missing route check: {required}")
    if not find_token_sequence(trigger_tokens, sponsor_type_gate):
        errors.append("monthly settlement validity must enforce the sponsor country types")
    if not find_token_sequence(
        trigger_tokens,
        script_tokens(
            "$COUNTRY$ = { "
            "ffcs_uses_cultural_settlement_law = yes"
        ),
    ):
        errors.append("monthly settlement validity must retain both supported laws")
    if cap_trigger.count("ffcs_uses_cultural_settlement_law") != 2:
        errors.append("two-law trigger must have one definition and one project-validity call")
    if cap_trigger.count("has_strategic_region_interest_tier") != 1:
        errors.append("strategic-region interest must be checked only when a project starts")
    if not find_token_sequence(
        trigger_tokens,
        script_tokens("strategic_region = $REGION$"),
    ):
        errors.append("settlement eligibility must receive its strategic region explicitly")
    if re.search(r"\$[A-Z_]+\$\.", cap_trigger):
        errors.append("script parameters must not use unsupported chained access")
    if len(
        find_token_sequence(
            trigger_tokens,
            script_tokens("$COUNTRY$ = { has_strategic_adjacency = $STATE$ }"),
        )
    ) != 1:
        errors.append("overseas entry must require direct strategic adjacency")
    if any(
        token.lower() == "root" or token.lower().startswith("root.")
        for token in trigger_tokens
    ):
        errors.append("state-scoped settlement triggers must not depend on caller root scope")

    settlement_effects = (
        root / "common" / "scripted_effects" / "ffcs_settlement_effects.txt"
    ).read_text(encoding="utf-8-sig")
    settlement_effect_tokens = script_tokens(settlement_effects)
    if re.search(
        r"(?:COUNTRY|TARGET)\s*=\s*var:ffcs_settlement_",
        cap_trigger + settlement_effects,
    ):
        errors.append("nested settlement checks must use restored country scopes, not local var links")
    for required in (
        "ffcs_apply_settlement_phase_v2 = { DIVISOR = 4 }",
        "ffcs_apply_settlement_phase_v2 = { DIVISOR = 3 }",
        "ffcs_apply_settlement_phase_v2 = { DIVISOR = 2 }",
        "ffcs_apply_settlement_phase_v2 = { DIVISOR = 1 }",
        "clear_variable_list = ffcs_settlement_provinces_v2",
        "remove_variable = ffcs_settlement_route_v2",
        "state_region = { remove_variable = ffcs_settlement_sponsor_v1 }",
        "create_building = { building = building_port level = 1 }",
        "limit = { ffcs_generated_has_land_seed_v2 = { COUNTRY = scope:ffcs_settlement_sponsor TARGET = scope:ffcs_settlement_original_owner } } scope:ffcs_settlement_project = { set_variable = { name = ffcs_settlement_route_v2 value = 1 } } ffcs_generated_take_land_seed_v2 = { COUNTRY = scope:ffcs_settlement_sponsor TARGET = scope:ffcs_settlement_original_owner PROJECT = scope:ffcs_settlement_project }",
        "limit = { ffcs_generated_has_port_seed_v2 = { TARGET = scope:ffcs_settlement_original_owner } } scope:ffcs_settlement_project = { set_variable = { name = ffcs_settlement_route_v2 value = 2 } } ffcs_generated_take_port_seed_v2 = { COUNTRY = scope:ffcs_settlement_sponsor TARGET = scope:ffcs_settlement_original_owner PROJECT = scope:ffcs_settlement_project }",
        "change_variable = { name = ffcs_settlement_progress_v1 add = ffcs_monthly_settlement_progress_value }",
        "save_temporary_scope_as = ffcs_settlement_state",
        "save_temporary_scope_as = ffcs_settlement_project",
        "save_temporary_scope_as = ffcs_settlement_target_state",
        "state.owner = scope:ffcs_settlement_sponsor",
        "ffcs_settlement_project_remains_valid = { COUNTRY = scope:ffcs_settlement_sponsor TARGET = scope:ffcs_settlement_original_owner }",
        "scope:ffcs_settlement_target_state = { ffcs_apply_monthly_settlement_progress_v1 = yes }",
        "var:ffcs_settlement_phase_v1 >= 1 OR = { NOT = { has_variable_list = ffcs_settlement_provinces_v2 }",
        "clear_variable_list = ffcs_settlement_provinces_v2 set_variable = { name = ffcs_settlement_phase_v1 value = 0 }",
    ):
        if not find_token_sequence(settlement_effect_tokens, script_tokens(required)):
            errors.append(f"settlement phase state machine missing: {required}")
    if not re.search(
        r"ffcs_settlement_progress_v1\s*>=\s*95.*?"
        r"ffcs_apply_settlement_phase_v2\s*=\s*\{\s*DIVISOR\s*=\s*1",
        settlement_effects,
        re.DOTALL,
    ):
        errors.append("contiguous phase 4 must be applied at 95 progress")

    for phase in (2, 3, 4):
        if settlement_effects.count(
            f"post_notification = ffcs_settlement_phase_{phase}"
        ) != 1:
            errors.append(f"settlement phase {phase} must post exactly one notification")
    for target in (
        "scope:ffcs_settlement_state",
        "scope:ffcs_settlement_project",
    ):
        required = (
            "remove_list_variable = { "
            "name = ffcs_active_settlement_states_v1 "
            f"target = {target} }}"
        )
        if not find_token_sequence(settlement_effect_tokens, script_tokens(required)):
            errors.append(f"settlement cleanup must unregister project state: {target}")

    if "local_var:ffcs_monthly_progress_points" in settlement_effects:
        errors.append("monthly progress must use a directly supported change-variable value block")

    settlement_values = (
        root / "common" / "script_values" / "ffcs_settlement_values.txt"
    ).read_text(encoding="utf-8-sig")
    settlement_value_tokens = script_tokens(settlement_values)
    for required in (
        "ffcs_monthly_settlement_progress_value = { save_temporary_scope_as = ffcs_value_state",
        "add = 0.5",
        "value = scope:ffcs_value_sponsor.gdp divide = 100000000 max = 2",
        "institution = institution_colonial_affairs value >= 5",
        "has_technology_researched = quinine",
        "has_technology_researched = civilizing_mission",
        "is_adjacent_to_state = scope:ffcs_value_state",
        "turmoil >= 0.25",
        "has_state_trait = state_trait_severe_malaria",
        "value = scope:ffcs_value_sponsor.var:ffcs_active_settlement_count_v1",
        "min = 0.25",
        "ffcs_settlement_progress_fraction = {",
        "ffcs_settlement_phase_value = {",
        "ffcs_settlement_resistance_value = {",
        "ffcs_settlement_route_value = {",
    ):
        if not find_token_sequence(settlement_value_tokens, script_tokens(required)):
            errors.append(f"shared settlement value missing: {required}")

    on_actions = (
        root / "common" / "on_actions" / "ffcs_settlement_on_actions.txt"
    ).read_text(encoding="utf-8-sig")
    on_action_tokens = script_tokens(on_actions)
    diagnostic_text = "\n".join((diplomatic_action, settlement_effects, on_actions))
    for marker in (
        "PROJECT_CREATED",
        "SCHEDULER_REACHED",
        "EVALUATION_PASSED",
        "EVALUATION_FAILED",
        "PHASE_SWEEP_FINISHED",
        "PROJECT_COMPLETED",
        "PROJECT_CANCELLED",
    ):
        if f"FFCS|{marker}" not in diagnostic_text:
            errors.append(f"runtime diagnostic marker missing: FFCS|{marker}")
    for required in (
        "on_monthly_pulse_country = { on_actions = { ffcs_monthly_country_pulse_v1 } }",
        "limit = { has_variable = ffcs_active_settlement_count_v1 } save_temporary_scope_as = ffcs_monthly_sponsor",
        "set_variable = { name = ffcs_active_settlement_count_v1 value = 0 }",
        "clear_variable_list = ffcs_active_settlement_states_v1",
        "change_variable = { name = ffcs_active_settlement_count_v1 add = 1 }",
        "add_to_variable_list = { name = ffcs_active_settlement_states_v1 target = prev }",
        "state_region = { set_variable = { name = ffcs_settlement_sponsor_v1 value = scope:ffcs_monthly_sponsor } }",
        "add_journal_entry = { type = je_ffcs_cultural_settlement_overview }",
        "every_state = { limit = { has_variable = ffcs_settlement_sponsor_v1 var:ffcs_settlement_sponsor_v1 ?= scope:ffcs_monthly_sponsor } ffcs_advance_settlement_project_v1 = yes }",
        "limit = { var:ffcs_active_settlement_count_v1 < 1 } remove_variable = ffcs_active_settlement_count_v1",
        "on_state_owner_change = { on_actions = { ffcs_cancel_project_on_owner_change_v1 } }",
        "var:ffcs_settlement_sponsor_v1 ?= owner",
    ):
        if not find_token_sequence(on_action_tokens, script_tokens(required)):
            errors.append(f"settlement scheduler or owner-change injection missing: {required}")

    journal_entry = (
        root / "common" / "journal_entries" / "ffcs_settlement_journal_entries.txt"
    ).read_text(encoding="utf-8-sig")
    journal_tokens = script_tokens(journal_entry)
    for required in (
        "je_ffcs_cultural_settlement_overview = {",
        "group = je_group_foreign_affairs",
        'gui = "gui/journal_entry_widgets/ffcs_settlement_overview.gui"',
        'name = "widget_je_ffcs_cultural_settlement_overview"',
        'container = "custom_widget_container_3"',
        "invalid = { NOT = { has_variable = ffcs_active_settlement_count_v1 } }",
        "should_be_pinned_by_default_uninvolved_or_context = yes",
    ):
        if not find_token_sequence(journal_tokens, script_tokens(required)):
            errors.append(f"settlement overview journal entry missing: {required}")

    overview_gui = (
        root / "gui" / "journal_entry_widgets" / "ffcs_settlement_overview.gui"
    ).read_text(encoding="utf-8-sig")
    for required in (
        "JournalEntry.GetCountry.MakeScope.GetList('ffcs_active_settlement_states_v1')",
        "State.MakeScope.ScriptValue('ffcs_settlement_progress_fraction')",
        "State.MakeScope.ScriptValue('ffcs_monthly_settlement_progress_value')",
        "State.MakeScope.ScriptValue('ffcs_settlement_phase_value')",
        "State.MakeScope.ScriptValue('ffcs_settlement_resistance_value')",
        "State.MakeScope.ScriptValue('ffcs_settlement_route_value')",
        "InformationPanelBar.OpenStatePanel(State.AccessSelf)",
    ):
        if required not in overview_gui:
            errors.append(f"settlement overview widget missing: {required}")

    messages = (
        root / "common" / "messages" / "ffcs_settlement_messages.txt"
    ).read_text(encoding="utf-8-sig")
    for phase in (2, 3, 4):
        if messages.count(f"ffcs_settlement_phase_{phase} = {{") != 1:
            errors.append(f"settlement phase {phase} message definition missing")

    native_guard = (
        root / "common" / "laws" / "zzzzz_ffcs_colonial_resettlement_guard.txt"
    ).read_text(encoding="utf-8-sig")
    hard_off_values = [
        float(value)
        for value in re.findall(
        r"state_colony_growth_creation_factor\s*=\s*(-?\d+(?:\.\d+)?)",
        native_guard,
        )
    ]
    hard_off_value = max(hard_off_values) if hard_off_values else 0.0
    if len(hard_off_values) != 2 or any(value > -100 for value in hard_off_values):
        errors.append(
            "both cultural-settlement laws must hard-disable native colonial growth creation"
        )
    for law in ("law_colonial_resettlement", "law_frontier_colonization"):
        if f"REPLACE:{law}" not in native_guard:
            errors.append(f"native colonial-growth replacement missing for {law}")

    charter_guard = (
        root
        / "common"
        / "company_charter_types"
        / "zzzzz_ffcs_disable_native_colonization_charter.txt"
    ).read_text(encoding="utf-8-sig")
    if not all(
        token in charter_guard
        for token in (
            "REPLACE:colonization_charter",
            "NOT = { ffcs_uses_cultural_settlement_law = yes }",
        )
    ):
        errors.append(
            "colonization charter must be unavailable under both FFCS laws"
        )
    if charter_guard.count("ffcs_uses_cultural_settlement_law = yes") != 1:
        errors.append("colonization charter must contain exactly one shared law gate")
    charter_tokens = script_tokens(charter_guard)
    for required in (
        "possible = {",
        "owner ?= {",
        "NOT = { is_country_type = unrecognized }",
        "custom_tooltip = {",
    ):
        if not find_token_sequence(charter_tokens, script_tokens(required)):
            errors.append(f"colonization charter guard missing structure: {required}")
    if len(re.findall(r"(?m)^\s*possible\s*=\s*\{", charter_guard)) != 1:
        errors.append("colonization charter replacement must contain exactly one possible section")

    text_files = [
        path
        for path in root.rglob("*")
        if path.is_file()
        and path.suffix.lower() in {".txt", ".gui", ".yml", ".md", ".py", ".json"}
    ]
    for path in text_files:
        data = path.read_bytes()
        if b"\x00" in data:
            errors.append(f"{path.relative_to(root)}: contains NUL bytes")
        for line_number, line in enumerate(
            data.decode("utf-8-sig").splitlines(), start=1
        ):
            if line.rstrip(" \t") != line:
                errors.append(f"{path.relative_to(root)}:{line_number}: trailing whitespace")

    by_database: dict[str, list[tuple[str, Path]]] = {}
    for path in common_files:
        relative = path.relative_to(root / "common")
        database = relative.parts[0]
        by_database.setdefault(database, []).extend(
            (key, path) for key in top_level_keys(path)
        )
    for database, entries in sorted(by_database.items()):
        counts = Counter(key for key, _ in entries)
        for key, count in sorted(counts.items()):
            if count > 1:
                locations = sorted(
                    str(path.relative_to(root)) for found, path in entries if found == key
                )
                errors.append(
                    f"duplicate top-level key in common/{database}: {key} -> {locations}"
                )

    english = root / "localization" / "english" / "ffcs_cultural_settlement_l_english.yml"
    chinese = root / "localization" / "simp_chinese" / "ffcs_cultural_settlement_l_simp_chinese.yml"
    if args.fix_localization_bom:
        for path in (english, chinese):
            raw = path.read_bytes()
            if not raw.startswith(b"\xef\xbb\xbf"):
                path.write_bytes(b"\xef\xbb\xbf" + raw)

    en_keys, en_bom = localization_keys(english)
    zh_keys, zh_bom = localization_keys(chinese)
    if not en_bom or not zh_bom:
        errors.append("localization files must use UTF-8 BOM")
    if set(en_keys) != set(zh_keys):
        errors.append(
            "localization key mismatch: "
            f"English-only={sorted(set(en_keys) - set(zh_keys))}, "
            f"Chinese-only={sorted(set(zh_keys) - set(en_keys))}"
        )
    for language, keys in (("English", en_keys), ("Chinese", zh_keys)):
        duplicates = sorted(key for key, count in Counter(keys).items() if count > 1)
        if duplicates:
            errors.append(f"{language} duplicate localization keys: {duplicates}")

    debug_events = (root / "events" / "ffcs_debug_events.txt").read_text(
        encoding="utf-8-sig"
    )
    for required in (
        "ffcs_debug.1",
        "set_global_variable = ffcs_debug_enabled_v1",
        "ffcs_debug.2",
        "remove_global_variable = ffcs_debug_enabled_v1",
    ):
        if required not in debug_events:
            errors.append(f"debug event entry point missing: {required}")

    generated_effects = root / "common" / "scripted_effects" / "ffcs_generated_province_phases.txt"
    generated_triggers = root / "common" / "scripted_triggers" / "ffcs_generated_province_routes.txt"
    generated_effect_text = generated_effects.read_text(encoding="utf-8-sig")
    generated_trigger_text = generated_triggers.read_text(encoding="utf-8-sig")
    for dispatcher in (
        "ffcs_generated_take_land_seed_v2",
        "ffcs_generated_take_port_seed_v2",
        "ffcs_generated_transfer_frontier_sweep_v2",
    ):
        if dispatcher not in generated_effect_text:
            errors.append(f"generated effect dispatcher missing: {dispatcher}")
    for dispatcher in (
        "ffcs_generated_has_land_seed_v2",
        "ffcs_generated_has_port_seed_v2",
        "ffcs_generated_country_owns_port_v2",
        "ffcs_generated_has_frontier_v2",
    ):
        if dispatcher not in generated_trigger_text:
            errors.append(f"generated trigger dispatcher missing: {dispatcher}")
    if "root.owner" in generated_trigger_text:
        errors.append("generated seed triggers must receive the target owner explicitly")
    if "$PROJECT$ = {" not in generated_effect_text or "$PROJECT$ = {" not in generated_trigger_text:
        errors.append("generated province logic must receive the project carrier explicitly")
    for required in (
        "state.owner = $TARGET$",
        "state.owner = $COUNTRY$",
        "$PROJECT$ = { any_in_list = { variable = ffcs_settlement_provinces_v2",
        "$PROJECT$ = { add_to_variable_list = { name = ffcs_settlement_provinces_v2 target = p:x",
        "any_in_list = { variable = ffcs_settlement_provinces_v2",
    ):
        if required not in generated_effect_text:
            errors.append(f"generated frontier ownership check missing: {required}")

    manifest_path = root / "tools" / "generated_phase_manifest.json"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("generator_schema") != 2:
            errors.append("generated manifest schema must be 2")
        hashes = (
            (
                "effect_output_sha256",
                hashlib.sha256(generated_effect_text.encode()).hexdigest(),
            ),
            (
                "trigger_output_sha256",
                hashlib.sha256(generated_trigger_text.encode()).hexdigest(),
            ),
        )
        for key, actual in hashes:
            if manifest.get(key) != actual:
                errors.append(f"generated output does not match manifest: {key}")
        transfer_blocks = re.findall(
            r"set_owner_of_provinces\s*=\s*\{.*?"
            r"provinces\s*=\s*\{\s*x([0-9A-Fa-f]{6})\s*\}",
            generated_effect_text,
            re.DOTALL,
        )
        if len(transfer_blocks) != manifest.get("transfer_branch_count"):
            errors.append("generated transfer branch count does not match manifest")
        if re.search(r'provinces\s*=\s*\{\s*"x[0-9A-Fa-f]{6}"', generated_effect_text):
            errors.append("generated province effects must use unquoted database IDs")
        state_total = sum(
            state.get("province_count", 0)
            for state in manifest.get("states", {}).values()
        )
        if state_total != manifest.get("province_count"):
            errors.append("generated state-region province accounting is incomplete")

    stack_arguments = (
        args.game_root,
        args.tech_res_root,
        args.firefall_root,
        args.core_balance_root,
    )
    stack_report: list[str] = []
    if any(stack_arguments):
        if not all(stack_arguments):
            errors.append(
                "final-stack validation requires --game-root, --tech-res-root, "
                "--firefall-root and --core-balance-root together"
            )
        else:
            stack_errors, stack_report = validate_final_stack(
                [
                    StackRoot("game", args.game_root.resolve()),
                    StackRoot("tech_res", args.tech_res_root.resolve()),
                    StackRoot("firefall", args.firefall_root.resolve()),
                    StackRoot("core_balance", args.core_balance_root.resolve()),
                ],
                root,
                hard_off_value,
            )
            errors.extend(stack_errors)

    if errors:
        print("VALIDATION FAILED")
        for error in errors:
            print(f"- {error}")
        return 1
    print(f"Validation passed: {len(en_keys)} localization keys, metadata and script structure OK")
    for line in stack_report:
        print(f"- {line}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
