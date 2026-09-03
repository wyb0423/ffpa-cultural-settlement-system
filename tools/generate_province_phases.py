#!/usr/bin/env python3
"""Generate literal province-route dispatchers from the final map database."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import deque
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image


PROVINCE = re.compile(r'"x([0-9A-Fa-f]{6})"')
PORT = re.compile(r'^\s*port\s*=\s*"x([0-9A-Fa-f]{6})"', re.MULTILINE)
BLOCK_START = re.compile(r'^\s*(STATE_[A-Za-z0-9_]+)\s*=\s*\{', re.MULTILINE)


@dataclass(frozen=True)
class StateRegion:
    name: str
    provinces: tuple[int, ...]
    port: int | None


def extract_blocks(text: str) -> list[tuple[str, str]]:
    blocks: list[tuple[str, str]] = []
    for match in BLOCK_START.finditer(text):
        depth = 1
        index = match.end()
        in_string = False
        escaped = False
        while index < len(text) and depth:
            char = text[index]
            if in_string:
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == '"':
                    in_string = False
            elif char == '"':
                in_string = True
            elif char == "#":
                newline = text.find("\n", index)
                index = len(text) if newline < 0 else newline
                continue
            elif char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
            index += 1
        if depth:
            raise ValueError(f"Unclosed state-region block {match.group(1)}")
        blocks.append((match.group(1), text[match.end() : index - 1]))
    return blocks


def parse_state_regions(directory: Path) -> tuple[list[StateRegion], dict[int, list[str]]]:
    regions: list[StateRegion] = []
    names: set[str] = set()
    occurrences: dict[int, list[str]] = {}
    for path in sorted(directory.glob("*.txt")):
        text = path.read_text(encoding="utf-8-sig")
        for name, body in extract_blocks(text):
            if name in names:
                raise ValueError(f"Duplicate state region {name}")
            match = re.search(r"\bprovinces\s*=\s*\{([^}]*)\}", body, re.DOTALL)
            if not match:
                continue
            provinces = tuple(
                sorted({int(value, 16) for value in PROVINCE.findall(match.group(1))})
            )
            if not provinces:
                continue
            port_match = PORT.search(body)
            port = int(port_match.group(1), 16) if port_match else None
            if port not in provinces:
                port = None
            for province_id in provinces:
                occurrences.setdefault(province_id, []).append(name)
            names.add(name)
            regions.append(StateRegion(name, provinces, port))
    duplicates = {
        province_id: owners
        for province_id, owners in occurrences.items()
        if len(owners) > 1
    }
    return sorted(regions, key=lambda region: region.name), duplicates


def build_adjacency(image_path: Path, provinces: set[int]) -> dict[int, set[int]]:
    adjacency = {province_id: set() for province_id in provinces}
    image = np.asarray(Image.open(image_path).convert("RGB"), dtype=np.uint32)
    ids = (image[:, :, 0] << 16) | (image[:, :, 1] << 8) | image[:, :, 2]
    boundaries = (
        (ids[:, :-1], ids[:, 1:]),
        (ids[:-1, :], ids[1:, :]),
        (ids[:, -1:], ids[:, :1]),
    )
    for left, right in boundaries:
        mask = left != right
        for first, second in zip(left[mask].tolist(), right[mask].tolist()):
            if first in adjacency and second in adjacency:
                adjacency[first].add(second)
                adjacency[second].add(first)
    return adjacency


def resolve_duplicate_provinces(
    regions: list[StateRegion],
    duplicates: dict[int, list[str]],
    adjacency: dict[int, set[int]],
) -> tuple[list[StateRegion], dict[str, str]]:
    duplicate_ids = set(duplicates)
    unique_owner = {
        province_id: region.name
        for region in regions
        for province_id in region.provinces
        if province_id not in duplicate_ids
    }
    resolutions: dict[int, str] = {}
    for province_id, owners in sorted(duplicates.items()):
        scores = {
            owner: sum(
                unique_owner.get(neighbour) == owner
                for neighbour in adjacency[province_id]
            )
            for owner in owners
        }
        resolutions[province_id] = min(owners, key=lambda owner: (-scores[owner], owner))

    resolved: list[StateRegion] = []
    for region in regions:
        provinces = tuple(
            province_id
            for province_id in region.provinces
            if resolutions.get(province_id, region.name) == region.name
        )
        if provinces:
            resolved.append(
                StateRegion(
                    region.name,
                    provinces,
                    region.port if region.port in provinces else None,
                )
            )
    return resolved, {
        f"x{province_id:06X}": owner
        for province_id, owner in sorted(resolutions.items())
    }


def validate_adjacency(adjacency: dict[int, set[int]]) -> None:
    for province_id, neighbours in adjacency.items():
        if province_id in neighbours:
            raise ValueError(f"Province x{province_id:06X} is adjacent to itself")
        for neighbour in neighbours:
            if province_id not in adjacency[neighbour]:
                raise ValueError(
                    f"Asymmetric edge x{province_id:06X}-x{neighbour:06X}"
                )


def component_count(region: StateRegion, adjacency: dict[int, set[int]]) -> int:
    remaining = set(region.provinces)
    count = 0
    while remaining:
        count += 1
        queue = deque([min(remaining)])
        remaining.remove(queue[0])
        while queue:
            current = queue.popleft()
            for neighbour in adjacency[current]:
                if neighbour in remaining:
                    remaining.remove(neighbour)
                    queue.append(neighbour)
    return count


def p(province_id: int) -> str:
    return f"p:x{province_id:06X}"


def owner_neighbours(neighbours: tuple[int, ...], owner: str) -> str:
    tests = " ".join(f"{p(neighbour)}.state.owner = {owner}" for neighbour in neighbours)
    return f"OR = {{ {tests} }}"


def project_neighbours(neighbours: tuple[int, ...]) -> str:
    identities = " ".join(f"this = {p(neighbour)}" for neighbour in neighbours)
    return (
        "any_in_list = { variable = ffcs_settlement_provinces_v2 "
        f"state.owner = $COUNTRY$ OR = {{ {identities} }} }}"
    )


def grouped_trigger(
    name: str,
    regions: list[StateRegion],
    candidates: dict[str, list[tuple[int, tuple[int, ...]]]],
    candidate_owner: str,
    neighbour_test,
    comment: str,
) -> list[str]:
    lines = [comment, f"{name} = {{", "\tOR = {"]
    for region in regions:
        entries = candidates[region.name]
        if not entries:
            continue
        lines.extend(["\t\tAND = {", f"\t\t\tstate_region = s:{region.name}", "\t\t\tOR = {"])
        for candidate, neighbours in entries:
            lines.append(
                f"\t\t\t\tAND = {{ {p(candidate)}.state.owner = {candidate_owner} "
                f"{neighbour_test(neighbours)} }}"
            )
        lines.extend(["\t\t\t}", "\t\t}"])
    lines.extend(["\t}", "}", ""])
    return lines


def transfer(candidate: int) -> str:
    return (
        "add_to_variable_list = { "
        f"name = ffcs_settlement_provinces_v2 target = {p(candidate)} "
        "} "
        "state_region = { set_owner_of_provinces = { "
        f'country = $COUNTRY$ provinces = {{ "x{candidate:06X}" }} '
        "} } "
        "change_variable = { name = ffcs_transfer_budget_v2 add = -1 }"
    )


def grouped_effect(
    name: str,
    regions: list[StateRegion],
    candidates: dict[str, list[tuple[int, tuple[int, ...]]]],
    neighbour_test,
    *,
    one_only: bool,
    comment: str,
) -> list[str]:
    lines = [comment, f"{name} = {{"]
    outer_branch = 0
    for region in regions:
        entries = candidates[region.name]
        if not entries:
            continue
        keyword = "if" if outer_branch == 0 else "else_if"
        lines.extend(
            [
                f"\t{keyword} = {{",
                f"\t\tlimit = {{ state_region = s:{region.name} }}",
            ]
        )
        inner_branch = 0
        for candidate, neighbours in entries:
            inner_keyword = (
                "if" if not one_only or inner_branch == 0 else "else_if"
            )
            lines.append(
                f"\t\t{inner_keyword} = {{ limit = {{ "
                "var:ffcs_transfer_budget_v2 > 0 num_provinces > 1 "
                f"{p(candidate)}.state.owner = $TARGET$ "
                f"{neighbour_test(neighbours)} }} {transfer(candidate)} }}"
            )
            inner_branch += 1
        lines.append("\t}")
        outer_branch += 1
    lines.extend(["}", ""])
    return lines


def render_outputs(
    regions: list[StateRegion], adjacency: dict[int, set[int]]
) -> tuple[str, str, dict[str, int]]:
    land: dict[str, list[tuple[int, tuple[int, ...]]]] = {}
    frontier: dict[str, list[tuple[int, tuple[int, ...]]]] = {}
    for region in regions:
        region_ids = set(region.provinces)
        land[region.name] = [
            (province_id, tuple(sorted(adjacency[province_id])))
            for province_id in region.provinces
            if adjacency[province_id]
        ]
        frontier[region.name] = [
            (
                province_id,
                tuple(sorted(adjacency[province_id].intersection(region_ids))),
            )
            for province_id in region.provinces
            if adjacency[province_id].intersection(region_ids)
        ]

    trigger_lines = [
        "# AUTO-GENERATED by tools/generate_province_phases.py; do not edit.",
        "# Literal province topology for route and frontier checks.",
        "",
    ]
    trigger_lines += grouped_trigger(
        "ffcs_generated_has_land_seed_v2",
        regions,
        land,
        "root.owner",
        lambda neighbours: owner_neighbours(neighbours, "$COUNTRY$"),
        "# Root = target state; COUNTRY = sponsor",
    )
    trigger_lines.extend(
        [
            "# Root = target state",
            "ffcs_generated_has_port_seed_v2 = {",
            "\tOR = {",
        ]
    )
    for region in regions:
        if region.port is not None:
            trigger_lines.append(
                f"\t\tAND = {{ state_region = s:{region.name} "
                f"{p(region.port)}.state.owner = root.owner }}"
            )
    trigger_lines.extend(["\t}", "}", ""])
    trigger_lines.extend(
        [
            "# Root = target state; COUNTRY = country to test",
            "ffcs_generated_country_owns_port_v2 = {",
            "\tOR = {",
        ]
    )
    for region in regions:
        if region.port is not None:
            trigger_lines.append(
                f"\t\tAND = {{ state_region = s:{region.name} "
                f"{p(region.port)}.state.owner = $COUNTRY$ }}"
            )
    trigger_lines.extend(["\t}", "}", ""])
    trigger_lines += grouped_trigger(
        "ffcs_generated_has_frontier_v2",
        regions,
        frontier,
        "$TARGET$",
        project_neighbours,
        "# Root = target state; COUNTRY = sponsor; TARGET = original owner",
    )

    effect_lines = [
        "# AUTO-GENERATED by tools/generate_province_phases.py; do not edit.",
        "# ponytail: repeated scan is O(n^2) only at phase thresholds;",
        "# replace only if runtime profiling shows a material phase-tick cost.",
        "",
    ]
    effect_lines += grouped_effect(
        "ffcs_generated_take_land_seed_v2",
        regions,
        land,
        lambda neighbours: owner_neighbours(neighbours, "$COUNTRY$"),
        one_only=True,
        comment="# Root = target state; COUNTRY = sponsor; TARGET = original owner",
    )

    effect_lines.extend(
        [
            "# Root = target state; COUNTRY = sponsor; TARGET = original owner",
            "ffcs_generated_take_port_seed_v2 = {",
        ]
    )
    branch = 0
    for region in regions:
        if region.port is None:
            continue
        keyword = "if" if branch == 0 else "else_if"
        effect_lines.append(
            f"\t{keyword} = {{ limit = {{ state_region = s:{region.name} "
            "var:ffcs_transfer_budget_v2 > 0 num_provinces > 1 "
            f"{p(region.port)}.state.owner = $TARGET$ }} "
            f"{transfer(region.port)} }}"
        )
        branch += 1
    effect_lines.extend(["}", ""])
    effect_lines += grouped_effect(
        "ffcs_generated_transfer_frontier_sweep_v2",
        regions,
        frontier,
        project_neighbours,
        one_only=False,
        comment="# Root = target state; COUNTRY = sponsor; TARGET = original owner",
    )

    counts = {
        "land_seed_candidate_count": sum(map(len, land.values())),
        "frontier_candidate_count": sum(map(len, frontier.values())),
        "port_seed_count": sum(region.port is not None for region in regions),
    }
    return "\n".join(trigger_lines), "\n".join(effect_lines), counts


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser()
    parser.add_argument("--state-regions", required=True, type=Path)
    parser.add_argument("--provinces-image", required=True, type=Path)
    parser.add_argument(
        "--effects-output",
        type=Path,
        default=root
        / "common"
        / "scripted_effects"
        / "generated"
        / "ffcs_generated_province_phases.txt",
    )
    parser.add_argument(
        "--triggers-output",
        type=Path,
        default=root
        / "common"
        / "scripted_triggers"
        / "generated"
        / "ffcs_generated_province_routes.txt",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path(__file__).resolve().with_name("generated_phase_manifest.json"),
    )
    args = parser.parse_args()

    regions, duplicates = parse_state_regions(args.state_regions)
    all_provinces = {province_id for region in regions for province_id in region.provinces}
    adjacency = build_adjacency(args.provinces_image, all_provinces)
    validate_adjacency(adjacency)
    regions, duplicate_resolutions = resolve_duplicate_provinces(
        regions, duplicates, adjacency
    )
    resolved = {province_id for region in regions for province_id in region.provinces}
    adjacency = {
        province_id: neighbours.intersection(resolved)
        for province_id, neighbours in adjacency.items()
        if province_id in resolved
    }
    validate_adjacency(adjacency)

    triggers, effects, counts = render_outputs(regions, adjacency)
    for path, text in (
        (args.triggers_output, triggers),
        (args.effects_output, effects),
    ):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8", newline="\n")

    manifest = {
        "generator_schema": 2,
        "state_region_count": len(regions),
        "province_count": len(resolved),
        "adjacency_edge_count": sum(map(len, adjacency.values())) // 2,
        "internal_adjacency_edge_count": sum(
            len(adjacency[province_id].intersection(region.provinces))
            for region in regions
            for province_id in region.provinces
        )
        // 2,
        **counts,
        "transfer_branch_count": (
            counts["land_seed_candidate_count"]
            + counts["frontier_candidate_count"]
            + counts["port_seed_count"]
        ),
        "disconnected_state_region_count": sum(
            component_count(region, adjacency) > 1 for region in regions
        ),
        "duplicate_province_resolutions": duplicate_resolutions,
        "trigger_output_sha256": hashlib.sha256(triggers.encode()).hexdigest(),
        "effect_output_sha256": hashlib.sha256(effects.encode()).hexdigest(),
        "states": {
            region.name: {
                "province_count": len(region.provinces),
                "port": f"x{region.port:06X}" if region.port is not None else None,
                "component_count": component_count(region, adjacency),
            }
            for region in regions
        },
    }
    args.manifest.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(
        f"Generated {len(regions)} state regions, {len(resolved)} provinces, "
        f"{manifest['adjacency_edge_count']} edges"
    )


if __name__ == "__main__":
    main()
