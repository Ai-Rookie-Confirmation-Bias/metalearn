"""seed_profiles.weaknesses — string(legacy) / object 형식 호환."""
from __future__ import annotations

from typing import Any


def weakness_concept_id(entry: Any) -> str:
    if isinstance(entry, str):
        return entry
    if isinstance(entry, dict):
        return str(entry.get("concept_id") or "")
    return ""


def weakness_concept_ids(weaknesses: list[Any] | None) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for entry in weaknesses or []:
        concept_id = weakness_concept_id(entry)
        if concept_id and concept_id not in seen:
            seen.add(concept_id)
            result.append(concept_id)
    return result


def weakness_id_set(weaknesses: list[Any] | None) -> set[str]:
    return set(weakness_concept_ids(weaknesses))


def normalize_weakness_entry(entry: Any) -> dict[str, str]:
    if isinstance(entry, str):
        return {
            "concept_id": entry,
            "missing_concept": entry,
            "reason": "",
        }
    if isinstance(entry, dict):
        concept_id = str(entry.get("concept_id") or "")
        return {
            "concept_id": concept_id,
            "missing_concept": str(entry.get("missing_concept") or concept_id),
            "reason": str(entry.get("reason") or ""),
        }
    return {"concept_id": "", "missing_concept": "", "reason": ""}


def normalize_weaknesses(weaknesses: list[Any] | None) -> list[dict[str, str]]:
    seen: set[str] = set()
    result: list[dict[str, str]] = []
    for entry in weaknesses or []:
        normalized = normalize_weakness_entry(entry)
        concept_id = normalized["concept_id"]
        if not concept_id or concept_id in seen:
            continue
        seen.add(concept_id)
        result.append(normalized)
    return result


def remove_weakness(weaknesses: list[Any], concept_id: str) -> list[Any]:
    return [w for w in weaknesses if weakness_concept_id(w) != concept_id]


def upsert_weakness(weaknesses: list[Any], entry: dict[str, str]) -> list[Any]:
    concept_id = entry["concept_id"]
    return [*remove_weakness(weaknesses, concept_id), entry]
