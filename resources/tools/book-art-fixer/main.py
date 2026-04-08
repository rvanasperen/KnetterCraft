import json
import sys
from pathlib import Path
from dataclasses import dataclass
from typing import Dict, List, Tuple


ROOT = Path(__file__).parent


@dataclass(frozen=True)
class Case:
    conditions: Dict[str, int]
    model: str
    source: str # "lullaby" | "beautiful"


def load_json(path: Path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path: Path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def parse_lullaby(data) -> List[Case]:
    root = data.get("model")
    if not root:
        raise ValueError("[Lullaby] Missing root model")

    extracted: List[Case] = []

    def walk(node):
        node_type = node.get("type")

        if node_type == "minecraft:model":
            return

        if node_type != "minecraft:condition":
            raise ValueError(f"[Lullaby] Unsupported node type: {node_type}")

        value = node.get("value")
        if not isinstance(value, list) or len(value) == 0:
            raise ValueError("[Lullaby] Invalid value structure")

        entry = value[0]

        enchantment = entry.get("enchantments")
        levels = entry.get("levels", {})

        min_lvl = levels.get("min")
        max_lvl = levels.get("max")

        if not enchantment or min_lvl is None or max_lvl is None:
            raise ValueError("[Lullaby] Missing enchantment or level range")

        on_true = node.get("on_true")
        if not on_true or on_true.get("type") != "minecraft:model":
            raise ValueError("[Lullaby] on_true must be a model")

        model_path = on_true.get("model")

        for lvl in range(min_lvl, max_lvl + 1):
            extracted.append(
                Case(
                    conditions={enchantment: lvl},
                    model=model_path,
                    source="lullaby"
                )
            )

        on_false = node.get("on_false")
        if on_false:
            walk(on_false)

    walk(root)
    return extracted


def parse_beautiful(data) -> List[Case]:
    model = data.get("model", {})
    cases = model.get("cases", [])

    extracted: List[Case] = []

    for i, case in enumerate(cases):
        when = case.get("when")
        model_data = case.get("model", {})
        model_path = model_data.get("model")

        if not isinstance(when, dict):
            raise ValueError(f"[Beautiful] Case {i} has unexpected 'when': {when}")

        if not isinstance(model_path, str):
            raise ValueError(f"[Beautiful] Case {i} missing model path")

        extracted.append(
            Case(
                conditions=when,
                model=model_path,
                source="beautiful"
            )
        )

    return extracted


def case_key(case: Case) -> Tuple[Tuple[str, int], ...]:
    return tuple(sorted(case.conditions.items()))


def merge_cases(lullaby_cases: List[Case], beautiful_cases: List[Case]) -> List[Case]:
    merged: List[Case] = []
    seen = set()

    for case in lullaby_cases + beautiful_cases:
        key = case_key(case)

        if key in seen:
            continue

        seen.add(key)
        merged.append(case)

    return merged


def build_output(cases: List[Case]):
    return {
        "model": {
            "type": "minecraft:select",
            "property": "minecraft:component",
            "component": "minecraft:stored_enchantments",
            "cases": [
                {
                    "when": case.conditions,
                    "model": {
                        "type": "minecraft:model",
                        "model": case.model,
                    },
                }
                for case in cases
            ],
            "fallback": {
                "type": "minecraft:model",
                "model": "minecraft:item/enchanted_book",
            },
        }
    }


def print_summary(name: str, cases: List[Case]):
    print(f"{name}: {len(cases)} cases")


def detect_conflicts(lullaby_cases: List[Case], beautiful_cases: List[Case]):
    beautiful_map = {case_key(c): c for c in beautiful_cases}

    for c in lullaby_cases:
        k = case_key(c)
        if k in beautiful_map:
            other = beautiful_map[k]
            print(
                f"[WARN] Conflict on {dict(k)}:\n"
                f"  lullaby  -> {c.model}\n"
                f"  beautiful-> {other.model}"
            )


def main():
    lullaby_path = ROOT / "lullaby.json"
    beautiful_path=  ROOT / "beautiful.json"
    output_path = ROOT / "output.json"

    print("Loading input files")
    lullaby_json = load_json(lullaby_path)
    beautiful_json = load_json(beautiful_path)

    print("Parsing...")
    lullaby_cases = parse_lullaby(lullaby_json)
    beautiful_cases = parse_beautiful(beautiful_json)

    print_summary("Lullaby", lullaby_cases)
    print_summary("Beautiful", beautiful_cases)

    print("Checking conflicts...")
    detect_conflicts(lullaby_cases, beautiful_cases)

    print("Merging...")
    merged_cases = merge_cases(lullaby_cases, beautiful_cases)

    print(f"Merged total: {len(merged_cases)} cases")

    print("Building output...")
    output_json = build_output(merged_cases)

    print("Saving...")
    save_json(output_path, output_json)

    print(f"Done! Output written to {output_path}")


if __name__ == "__main__":
    main()
