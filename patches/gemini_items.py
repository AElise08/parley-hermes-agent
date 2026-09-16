"""Gemini array `items` placement — shared by the image patch and unit tests."""
from __future__ import annotations

from typing import Any, Dict


def place_items_on_array_branches(cleaned: Dict[str, Any]) -> None:
    """Gemini only allows ``items`` on ARRAY nodes.

    OpenAI-style tools often emit ``anyOf: [{type:string},{type:array}]`` plus a
    sibling ``items``. Leave that on the parent and Gemini 400s the whole
    request — every tool, not just the bad one. Hang ``items`` on each array
    branch and strip it from the parent.
    """
    items = cleaned.get("items")
    any_of = cleaned.get("anyOf")
    node_type = cleaned.get("type")
    if isinstance(any_of, list) and items is not None:
        cleaned.pop("items", None)
        for branch in any_of:
            if isinstance(branch, dict) and branch.get("type") == "array":
                branch.setdefault("items", items)
        return
    if node_type == "array" and not isinstance(items, dict):
        cleaned["items"] = {"type": "string"}
        return
    if node_type and node_type != "array":
        cleaned.pop("items", None)
