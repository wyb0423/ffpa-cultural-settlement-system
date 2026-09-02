#!/usr/bin/env python3
"""Generate deterministic contiguous settlement phases from final map data.

Requires Pillow and NumPy. Paths are supplied explicitly so no machine-specific
installation path is persisted in the mod.
"""

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
FIELD = re.compile(r'^\s*(port|city|farm|mine|wood)\s*=\s*"x([0-9A-Fa-f]{6})"', re.MULTILINE)
BLOCK_START = re.compile(r'^\s*(STATE_[A-Za-z0-9_]+)\s*=\s*\{', re.MULTILINE)


@dataclass(frozen=True)
class StateRegion:
    name: str
    provinces: tuple[int, ...]
    seed: int


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
    seen_names: set[str] = set()
    province_occurrences: dict[int, list[str]] = {}
    for path in sorted(directory.glob("*.txt")):
        text = path.read_text(encoding="utf-8-sig")
        for name, body in extract_blocks(text):
            if name in seen_names:
                raise ValueError(f"Duplicate state region {name}")
            provinces_match = re.search(r"\bprovinces\s*=\s*\{([^}]*)\}", body, re.DOTALL)
            if not provinces_match:
                continue
            provinces = tuple(
                sorted({int(value, 16) for value in PROVINCE.findall(provinces_match.group(1))})
            )
            if not provinces:
                continue
            fields = {key: int(value, 16) for key, value in FIELD.findall(body)}
            seed = next(
                (fields[key] for key in ("port", "city", "farm", "mine", "wood") if fields.get(key) in provinces),
                provinces[0],
            )
            for province in provinces:
                province_occurrences.setdefault(province, []).append(name)
            seen_names.add(name)
            regions.append(StateRegion(name=name, provinces=provinces, seed=seed))
    duplicates = {
        province: names
        for province, names in province_occurrences.items()
        if len(names) > 1
    }
    return sorted(regions, key=lambda region: region.name), duplicates


def build_adjacency(image_path: Path, provinces: set[int]) -> dict[int, set[int]]:
    adjacency = {province: set() for province in provinces}
    image = np.asarray(Image.open(image_path).convert("RGB"), dtype=np.uint32)
    province_ids = (image[:, :, 0] << 16) | (image[:, :, 1] << 8) | image[:, :, 2]

    boundary_sets = [
        (province_ids[:, :-1], province_ids[:, 1:]),
        (province_ids[:-1, :], province_ids[1:, :]),
        (province_ids[:, -1:], province_ids[:, :1]),
    ]
    for left, right in boundary_sets:
        mask = left != right
        for first, second in zip(left[mask].tolist(), right[mask].tolist()):
            if first not in adjacency or second not in adjacency:
                continue
            adjacency[first].add(second)
            adjacency[second].add(first)
    return adjacency


def resolve_duplicate_provinces(
    regions: list[StateRegion],
    duplicates: dict[int, list[str]],
    adjacency: dict[int, set[int]],
) -> tuple[list[StateRegion], dict[str, str]]:
    candidates = {
        province: set(names) for province, names in duplicates.items()
    }
    unique_owner = {
        province: region.name
        for region in regions
        for province in region.provinces
        if province not in candidates
    }
    resolutions: dict[int, str] = {}
    for province, names in sorted(candidates.items()):
        scores = {
            name: sum(
                1 for neighbour in adjacency[province] if unique_owner.get(neighbour) == name
            )
            for name in names
        }
        resolutions[province] = sorted(names, key=lambda name: (-scores[name], name))[0]

    resolved_regions: list[StateRegion] = []
    for region in regions:
        provinces = tuple(
            province
            for province in region.provinces
            if province not in resolutions or resolutions[province] == region.name
        )
        if not provinces:
            continue
        seed = region.seed if region.seed in provinces else provinces[0]
        resolved_regions.append(StateRegion(region.name, provinces, seed))
    return resolved_regions, {
        f"x{province:06X}": resolutions[province] for province in sorted(resolutions)
    }


def breadth_first_order(region: StateRegion, adjacency: dict[int, set[int]]) -> list[int]:
    remaining = set(region.provinces)
    ordered: list[int] = []
    component_seed = region.seed
    while remaining:
        if component_seed not in remaining:
            component_seed = min(remaining)
        queue = deque([component_seed])
        remaining.remove(component_seed)
        while queue:
            current = queue.popleft()
            ordered.append(current)
            for neighbour in sorted(adjacency[current]):
                if neighbour in remaining:
                    remaining.remove(neighbour)
                    queue.append(neighbour)
        if remaining:
            component_seed = min(remaining)
    return ordered


def component_count(region: StateRegion, adjacency: dict[int, set[int]]) -> int:
    remaining = set(region.provinces)
    count = 0
    while remaining:
        count += 1
        queue = deque([next(iter(remaining))])
        remaining.remove(queue[0])
        while queue:
            current = queue.popleft()
            for neighbour in adjacency[current]:
                if neighbour in remaining:
                    remaining.remove(neighbour)
                    queue.append(neighbour)
    return count


def split_phases(order: list[int]) -> tuple[tuple[int, ...], ...]:
    transferable = order[:-1]
    quotient, remainder = divmod(len(transferable), 4)
    phases: list[tuple[int, ...]] = []
    start = 0
    for phase in range(4):
        size = quotient + (1 if phase < remainder else 0)
        phases.append(tuple(transferable[start : start + size]))
        start += size
    return tuple(phases)


def render_dispatchers(assignments: dict[str, tuple[tuple[int, ...], ...]]) -> str:
    lines = [
        "# AUTO-GENERATED by tools/generate_province_phases.py; do not edit.",
        "# Each state region retains one province for final set_state_owner cleanup.",
        "",
    ]
    for phase_index in range(4):
        lines.append(f"ffcs_apply_generated_phase_{phase_index + 1} = {{")
        branch = 0
        for state_name in sorted(assignments):
            provinces = assignments[state_name][phase_index]
            if not provinces:
                continue
            keyword = "if" if branch == 0 else "else_if"
            lines.extend(
                [
                    f"\t{keyword} = {{",
                    f"\t\tlimit = {{ this = s:{state_name} }}",
                    "\t\tset_owner_of_provinces = {",
                    "\t\t\tcountry = $COUNTRY$",
                    "\t\t\tprovinces = {",
                ]
            )
            for offset in range(0, len(provinces), 10):
                values = " ".join(
                    f'"x{province:06X}"' for province in provinces[offset : offset + 10]
                )
                lines.append(f"\t\t\t\t{values}")
            lines.extend(["\t\t\t}", "\t\t}", "\t}"])
            branch += 1
        lines.extend(["}", ""])
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--state-regions", required=True, type=Path)
    parser.add_argument("--provinces-image", required=True, type=Path)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).resolve().parents[1]
        / "common"
        / "scripted_effects"
        / "generated"
        / "ffcs_generated_province_phases.txt",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path(__file__).resolve().with_name("generated_phase_manifest.json"),
    )
    args = parser.parse_args()

    regions, duplicates = parse_state_regions(args.state_regions)
    all_provinces = {province for region in regions for province in region.provinces}
    adjacency = build_adjacency(args.provinces_image, all_provinces)
    regions, duplicate_resolutions = resolve_duplicate_provinces(
        regions, duplicates, adjacency
    )
    assignments = {
        region.name: split_phases(breadth_first_order(region, adjacency))
        for region in regions
    }
    rendered = render_dispatchers(assignments)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(rendered, encoding="utf-8", newline="\n")

    manifest = {
        "generator_schema": 1,
        "state_region_count": len(regions),
        "province_count": sum(len(region.provinces) for region in regions),
        "transferred_province_count": sum(
            len(phase) for phases in assignments.values() for phase in phases
        ),
        "reserved_province_count": len(regions),
        "disconnected_state_region_count": sum(
            1 for region in regions if component_count(region, adjacency) > 1
        ),
        "duplicate_province_resolutions": duplicate_resolutions,
        "output_sha256": hashlib.sha256(rendered.encode("utf-8")).hexdigest(),
        "states": {
            region.name: {
                "province_count": len(region.provinces),
                "seed": f"x{region.seed:06X}",
                "phase_counts": [len(phase) for phase in assignments[region.name]],
                "reserved": f"x{breadth_first_order(region, adjacency)[-1]:06X}",
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
        f"Generated {len(regions)} state regions, "
        f"{manifest['province_count']} provinces, "
        f"{len(duplicate_resolutions)} duplicate resolution(s), "
        f"sha256={manifest['output_sha256']}"
    )


if __name__ == "__main__":
    main()
