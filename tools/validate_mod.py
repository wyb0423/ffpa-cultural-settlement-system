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
            "NOT = { has_law_or_variant = law_type:law_colonial_resettlement }"
        )
        gate_positions = find_token_sequence(target_tokens, gate_tokens)
        if len(gate_positions) != 1:
            errors.append(
                "FFCS AI table must contain exactly one Colonial Resettlement gate"
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
                    "AI table: exact Core Balance token parity plus one law gate"
                )

    law_provider = final_definition_provider(
        stack_roots, "laws", "law_colonial_resettlement"
    )
    charter_provider = final_definition_provider(
        stack_roots, "company_charter_types", "colonization_charter"
    )
    if law_provider is None:
        errors.append("final upstream law_colonial_resettlement provider not found")
    else:
        label, path = law_provider
        report.append(
            f"law provider: {label}:{path.relative_to(stack_roots[[r.label for r in stack_roots].index(label)].path)}"
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
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"metadata parse failed: {exc}")

    common_files = sorted((root / "common").rglob("*.txt"))
    for path in common_files:
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

    trigger_tokens = script_tokens(cap_trigger)
    if len(
        find_token_sequence(
            trigger_tokens,
            script_tokens("owner = { is_country_type = decentralized"),
        )
    ) < 2:
        errors.append("settlement entry and monthly validity must require a decentralized target")
    for required in (
        "var:ffcs_settlement_sponsor_v1 ?= { is_adjacent_to_state = root }",
        "var:ffcs_settlement_sponsor_v1 ?= { has_port_country = yes }",
    ):
        if not find_token_sequence(trigger_tokens, script_tokens(required)):
            errors.append(f"monthly settlement validity missing route check: {required}")
    if not find_token_sequence(trigger_tokens, sponsor_type_gate):
        errors.append("monthly settlement validity must enforce the sponsor country types")
    if cap_trigger.count("has_strategic_region_interest_tier") != 1:
        errors.append("strategic-region interest must be checked only when a project starts")

    settlement_effects = (
        root / "common" / "scripted_effects" / "ffcs_settlement_effects.txt"
    ).read_text(encoding="utf-8-sig")
    if not re.search(
        r"ffcs_settlement_progress_v1\s*>=\s*95.*?ffcs_apply_generated_phase_4",
        settlement_effects,
        re.DOTALL,
    ):
        errors.append("generated province phase 4 must be applied at 95 progress")

    native_guard = (
        root / "common" / "laws" / "zzzzz_ffcs_colonial_resettlement_guard.txt"
    ).read_text(encoding="utf-8-sig")
    hard_off = re.search(
        r"state_colony_growth_creation_factor\s*=\s*(-?\d+(?:\.\d+)?)",
        native_guard,
    )
    hard_off_value = float(hard_off.group(1)) if hard_off else 0.0
    if not hard_off or hard_off_value > -100:
        errors.append(
            "Colonial Resettlement must hard-disable native colonial growth creation"
        )

    charter_guard = (
        root
        / "common"
        / "company_charter_types"
        / "zzzzz_ffcs_disable_native_colonization_charter.txt"
    ).read_text(encoding="utf-8-sig")
    if not all(
        token in charter_guard
        for token in (
            "INJECT:colonization_charter",
            "has_law_or_variant = law_type:law_colonial_resettlement",
        )
    ):
        errors.append(
            "colonization charter must be unavailable under Colonial Resettlement"
        )
    charter_tokens = script_tokens(charter_guard)
    for required in (
        "possible = {",
        "owner ?= {",
        "NOT = { is_country_type = unrecognized }",
        "custom_tooltip = {",
    ):
        if not find_token_sequence(charter_tokens, script_tokens(required)):
            errors.append(f"colonization charter guard missing structure: {required}")

    text_files = [
        path
        for path in root.rglob("*")
        if path.is_file()
        and path.suffix.lower() in {".txt", ".yml", ".md", ".py", ".json"}
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

    generated = root / "common" / "scripted_effects" / "generated" / "ffcs_generated_province_phases.txt"
    generated_text = generated.read_text(encoding="utf-8-sig")
    for phase in range(1, 5):
        if f"ffcs_apply_generated_phase_{phase}" not in generated_text:
            errors.append(f"generated dispatcher missing phase {phase}")

    manifest_path = root / "tools" / "generated_phase_manifest.json"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        actual_hash = hashlib.sha256(generated.read_bytes()).hexdigest()
        if manifest.get("output_sha256") != actual_hash:
            errors.append("generated phase output does not match manifest hash")
        if manifest.get("province_count", 0) != (
            manifest.get("transferred_province_count", 0)
            + manifest.get("reserved_province_count", 0)
        ):
            errors.append("generated province accounting is incomplete")
        generated_provinces = re.findall(r'"x([0-9A-Fa-f]{6})"', generated_text)
        duplicate_generated = [
            province
            for province, count in Counter(generated_provinces).items()
            if count > 1
        ]
        if duplicate_generated:
            errors.append(
                f"generated provinces appear in multiple phases: {duplicate_generated[:10]}"
            )
        if len(generated_provinces) != manifest.get("transferred_province_count"):
            errors.append("generated province list count does not match manifest")

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
