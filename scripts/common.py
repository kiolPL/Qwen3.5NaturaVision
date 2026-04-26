from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator

ALLOWED_LICENSES = {"CC0", "CC-BY", "CC-BY-NC"}
LEGACY_SYSTEM_PROMPT = "You identify one forest organism from a fixed taxonomy and answer in JSON only."
LEGACY_USER_PROMPT = (
    "<image>Identify the organism. If it is not in the supported taxonomy or the image is ambiguous, "
    "return unknown."
)

PROMPT_STYLE_LEGACY_FULL_JSON = "legacy_full_json"
PROMPT_STYLE_STRICT_LABEL_ONLY = "strict_label_only"
PROMPT_STYLE_STRICT_LABEL_ONLY_WITH_TAXONOMY = "strict_label_only_with_taxonomy"
SUPPORTED_PROMPT_STYLES = (
    PROMPT_STYLE_LEGACY_FULL_JSON,
    PROMPT_STYLE_STRICT_LABEL_ONLY,
    PROMPT_STYLE_STRICT_LABEL_ONLY_WITH_TAXONOMY,
)

ASSISTANT_STYLE_FULL_JSON = "full_json"
ASSISTANT_STYLE_LABEL_ONLY = "label_only"
SUPPORTED_ASSISTANT_STYLES = (
    ASSISTANT_STYLE_FULL_JSON,
    ASSISTANT_STYLE_LABEL_ONLY,
)

EUROPE_BOXES = (
    (-25.0, 34.0, 45.0, 72.0),
    (-31.5, 63.0, -13.0, 67.5),
    (-11.0, 35.0, 5.0, 44.5),
)
POLAND_BOX = (14.05, 49.0, 24.25, 55.05)

UNKNOWN_RECORD = {
    "label_id": "unknown",
    "kingdom": "unknown",
    "scientific_name": "unknown",
    "polish_name": "nieznane",
    "english_name": "unknown",
}

INTERNAL_UNKNOWN_RECORDS = {
    "UNK_NON_TARGET_PLANT": {
        "label_id": "UNK_NON_TARGET_PLANT",
        "kingdom": "plants",
        "scientific_name": "unknown_non_target_plant",
        "polish_name": "nieznana roslina spoza taksonomii",
        "english_name": "unknown non-target plant",
        "public_label_id": "unknown",
    },
    "UNK_NON_TARGET_FUNGUS": {
        "label_id": "UNK_NON_TARGET_FUNGUS",
        "kingdom": "fungi",
        "scientific_name": "unknown_non_target_fungus",
        "polish_name": "nieznany grzyb spoza taksonomii",
        "english_name": "unknown non-target fungus",
        "public_label_id": "unknown",
    },
    "UNK_OTHER_OR_AMBIGUOUS": {
        "label_id": "UNK_OTHER_OR_AMBIGUOUS",
        "kingdom": "unknown",
        "scientific_name": "unknown_other_or_ambiguous",
        "polish_name": "inne lub niejednoznaczne",
        "english_name": "other or ambiguous",
        "public_label_id": "unknown",
    },
}
INTERNAL_UNKNOWN_LABELS = tuple(INTERNAL_UNKNOWN_RECORDS.keys())
INTERNAL_UNKNOWN_COLLAPSE_MAP = {label_id: "unknown" for label_id in INTERNAL_UNKNOWN_LABELS}

HARD_NEGATIVE_PAIRS = (
    ("FUN_01", "FUN_02"),
    ("FUN_07", "FUN_08"),
    ("FUN_09", "FUN_10"),
    ("FUN_18", "FUN_19"),
    ("PLANT_01", "PLANT_02"),
    ("PLANT_17", "PLANT_18"),
)

# iNaturalist can expose some target taxa under accepted synonym names rather than the
# starter taxonomy names we keep in the project manifest.
SCIENTIFIC_NAME_ALIASES: dict[str, tuple[str, ...]] = {
    "Anemone nemorosa": ("Anemonoides nemorosa",),
}


@dataclass(frozen=True)
class SpeciesEntry:
    label_id: str
    kingdom: str
    scientific_name: str
    polish_name: str
    english_name: str


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def load_species_manifest(path: Path) -> list[SpeciesEntry]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {"label_id", "kingdom", "scientific_name", "polish_name", "english_name"}
        missing = required.difference(reader.fieldnames or [])
        if missing:
            raise ValueError(f"Manifest is missing required columns: {sorted(missing)}")
        rows = []
        for row in reader:
            rows.append(
                SpeciesEntry(
                    label_id=row["label_id"].strip(),
                    kingdom=row["kingdom"].strip().lower(),
                    scientific_name=row["scientific_name"].strip(),
                    polish_name=row["polish_name"].strip(),
                    english_name=row["english_name"].strip(),
                )
            )
    if len(rows) != 40:
        raise ValueError(f"Expected 40 taxa in the manifest, found {len(rows)}")
    return rows


def manifest_by_label(entries: Iterable[SpeciesEntry]) -> dict[str, SpeciesEntry]:
    return {entry.label_id: entry for entry in entries}


def manifest_by_scientific_name(entries: Iterable[SpeciesEntry]) -> dict[str, SpeciesEntry]:
    return {entry.scientific_name.casefold(): entry for entry in entries}


def manifest_lookup_rows(entries: Iterable[SpeciesEntry]) -> list[tuple[str, str, str, str, str]]:
    rows: list[tuple[str, str, str, str, str]] = []
    for entry in entries:
        rows.append(
            (
                entry.label_id,
                entry.kingdom,
                entry.scientific_name,
                entry.polish_name,
                entry.english_name,
            )
        )
        for alias_name in SCIENTIFIC_NAME_ALIASES.get(entry.scientific_name, ()):
            rows.append(
                (
                    entry.label_id,
                    entry.kingdom,
                    alias_name,
                    entry.polish_name,
                    entry.english_name,
                )
            )
    return rows


def label_catalog(entries: Iterable[SpeciesEntry]) -> dict[str, dict[str, str]]:
    catalog = {
        entry.label_id: {
            "label_id": entry.label_id,
            "kingdom": entry.kingdom,
            "scientific_name": entry.scientific_name,
            "polish_name": entry.polish_name,
            "english_name": entry.english_name,
        }
        for entry in entries
    }
    catalog["unknown"] = dict(UNKNOWN_RECORD)
    return catalog


def training_label_catalog(entries: Iterable[SpeciesEntry]) -> dict[str, dict[str, str]]:
    catalog = label_catalog(entries)
    for label_id, payload in INTERNAL_UNKNOWN_RECORDS.items():
        catalog[label_id] = dict(payload)
    return catalog


def public_label_id(label_id: str) -> str:
    return INTERNAL_UNKNOWN_COLLAPSE_MAP.get(label_id, label_id)


def classify_unknown_subclass(row: dict[str, str]) -> str:
    if row.get("label_id") != "unknown":
        return row["label_id"]
    kingdom = normalize_kingdom(row.get("kingdom"))
    if kingdom == "plants":
        return "UNK_NON_TARGET_PLANT"
    if kingdom == "fungi":
        return "UNK_NON_TARGET_FUNGUS"
    return "UNK_OTHER_OR_AMBIGUOUS"


def taxonomy_lines(catalog: dict[str, dict[str, str]]) -> list[str]:
    uses_internal_unknown = catalog_has_internal_unknown(catalog)
    lines = []
    for label_id, payload in catalog.items():
        if label_id == "unknown":
            continue
        if label_id in INTERNAL_UNKNOWN_LABELS:
            lines.append(
                f"- {label_id} = {payload['english_name']} (collapse to public unknown outside training)"
            )
        else:
            lines.append(f"- {label_id} = {payload['scientific_name']}")
    if uses_internal_unknown:
        lines.append("- unknown = fallback public label after collapsing any UNK_* prediction")
    else:
        lines.append("- unknown = fallback label for any unsupported or ambiguous image")
    return lines


def catalog_has_internal_unknown(catalog: dict[str, dict[str, str]]) -> bool:
    return any(label_id in catalog for label_id in INTERNAL_UNKNOWN_LABELS)


def build_system_prompt(prompt_style: str, catalog: dict[str, dict[str, str]]) -> str:
    uses_internal_unknown = catalog_has_internal_unknown(catalog)
    if prompt_style == PROMPT_STYLE_LEGACY_FULL_JSON:
        return LEGACY_SYSTEM_PROMPT
    if prompt_style == PROMPT_STYLE_STRICT_LABEL_ONLY:
        fallback_text = (
            "Allowed outputs are the known label_ids and the internal UNK_* fallback labels only."
            if uses_internal_unknown
            else "Allowed outputs are the known label_ids and the public unknown fallback label only."
        )
        return (
            "You classify exactly one forest organism from a fixed taxonomy. "
            "Return JSON only with the single key label_id. "
            f"{fallback_text} "
            "Do not invent labels, synonyms, or alternate JSON keys."
        )
    if prompt_style == PROMPT_STYLE_STRICT_LABEL_ONLY_WITH_TAXONOMY:
        fallback_rule = (
            "If the organism is outside the supported taxonomy or the image is ambiguous, choose the best matching UNK_* label."
            if uses_internal_unknown
            else "If the organism is outside the supported taxonomy or the image is ambiguous, choose unknown."
        )
        rules = [
            "You classify exactly one forest organism from a fixed taxonomy.",
            "Return JSON only with the single key label_id.",
            "Choose exactly one allowed label_id from the list below.",
            fallback_rule,
            "Do not invent labels, synonyms, or alternate JSON keys.",
            "Allowed labels:",
            *taxonomy_lines(catalog),
        ]
        return "\n".join(rules)
    raise ValueError(f"Unsupported prompt_style: {prompt_style}")


def build_user_prompt(prompt_style: str, catalog: dict[str, dict[str, str]]) -> str:
    if prompt_style == PROMPT_STYLE_LEGACY_FULL_JSON:
        return LEGACY_USER_PROMPT
    if catalog_has_internal_unknown(catalog):
        unknown_text = "If no known label fits, return the best matching UNK_* label."
    else:
        unknown_text = "If no known label fits, return unknown."
    return (
        "<image>Classify the organism using the fixed taxonomy. "
        f"Return JSON only. {unknown_text}"
    )


def normalize_license(raw_value: str | None) -> str | None:
    if raw_value is None:
        return None
    text = raw_value.strip().lower()
    if not text:
        return None
    text = (
        text.replace("creative commons", "cc")
        .replace("creativecommons", "cc")
        .replace("_", "-")
        .replace(" ", "")
    )
    if text.startswith("cc0") or text == "publicdomain":
        return "CC0"
    if text.startswith("cc-by-nc"):
        return "CC-BY-NC"
    if text.startswith("cc-by"):
        return "CC-BY"
    if text in {"by", "ccby"}:
        return "CC-BY"
    if text in {"cc-bync", "ccbync"}:
        return "CC-BY-NC"
    return None


def normalize_kingdom(raw_value: str | None) -> str | None:
    if raw_value is None:
        return None
    text = raw_value.strip().casefold()
    if not text:
        return None
    if "fung" in text:
        return "fungi"
    if "plant" in text or "plantae" in text:
        return "plants"
    return None


def point_in_europe(latitude: float, longitude: float) -> bool:
    return any(
        min_lon <= longitude <= max_lon and min_lat <= latitude <= max_lat
        for min_lon, min_lat, max_lon, max_lat in EUROPE_BOXES
    )


def point_in_poland(latitude: float, longitude: float) -> bool:
    min_lon, min_lat, max_lon, max_lat = POLAND_BOX
    return min_lon <= longitude <= max_lon and min_lat <= latitude <= max_lat


def promote_inaturalist_image_url(url: str) -> str:
    upgraded = url.strip()
    for size in ("/square.", "/small.", "/medium.", "/original."):
        if size in upgraded:
            return upgraded.replace(size, "/large.")
    return upgraded


def build_response_payload(entry: SpeciesEntry | None) -> dict[str, str]:
    if entry is None:
        return {
            "label_id": "unknown",
            "kingdom": "unknown",
            "scientific_name": "unknown",
            "polish_name": "nieznane",
        }
    return {
        "label_id": entry.label_id,
        "kingdom": entry.kingdom,
        "scientific_name": entry.scientific_name,
        "polish_name": entry.polish_name,
    }


def build_response_payload_from_label(
    label_id: str,
    catalog: dict[str, dict[str, str]],
    assistant_style: str,
    *,
    collapse_internal_unknown: bool = False,
) -> dict[str, str]:
    resolved_label = public_label_id(label_id) if collapse_internal_unknown else label_id
    payload = catalog.get(resolved_label)
    if payload is None:
        raise KeyError(f"Unknown label_id: {label_id}")
    if assistant_style == ASSISTANT_STYLE_LABEL_ONLY:
        return {"label_id": resolved_label}
    return {
        "label_id": resolved_label,
        "kingdom": payload["kingdom"],
        "scientific_name": payload["scientific_name"],
        "polish_name": payload["polish_name"],
    }


def build_training_example_from_label(
    image_path: Path,
    label_id: str,
    catalog: dict[str, dict[str, str]],
    *,
    prompt_style: str = PROMPT_STYLE_LEGACY_FULL_JSON,
    assistant_style: str = ASSISTANT_STYLE_FULL_JSON,
    collapse_internal_unknown: bool = False,
) -> dict[str, object]:
    assistant_payload = json.dumps(
        build_response_payload_from_label(
            label_id,
            catalog,
            assistant_style,
            collapse_internal_unknown=collapse_internal_unknown,
        ),
        ensure_ascii=False,
    )
    return {
        "messages": [
            {"role": "system", "content": build_system_prompt(prompt_style, catalog)},
            {"role": "user", "content": build_user_prompt(prompt_style, catalog)},
            {"role": "assistant", "content": assistant_payload},
        ],
        "images": [str(image_path.resolve())],
    }


def build_training_example(image_path: Path, entry: SpeciesEntry | None) -> dict[str, object]:
    label_id = entry.label_id if entry is not None else "unknown"
    if entry is None:
        catalog = {"unknown": dict(UNKNOWN_RECORD)}
    else:
        catalog = {
            entry.label_id: {
                "label_id": entry.label_id,
                "kingdom": entry.kingdom,
                "scientific_name": entry.scientific_name,
                "polish_name": entry.polish_name,
                "english_name": entry.english_name,
            },
            "unknown": dict(UNKNOWN_RECORD),
        }
    return build_training_example_from_label(
        image_path=image_path,
        label_id=label_id,
        catalog=catalog,
        prompt_style=PROMPT_STYLE_LEGACY_FULL_JSON,
        assistant_style=ASSISTANT_STYLE_FULL_JSON,
    )


def read_jsonl(path: Path) -> Iterator[dict[str, object]]:
    with path.open("r", encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if line:
                yield json.loads(line)


def write_jsonl(path: Path, rows: Iterable[dict[str, object]]) -> None:
    ensure_parent(path)
    with path.open("w", encoding="utf-8", newline="") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False))
            handle.write("\n")
