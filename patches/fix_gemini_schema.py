#!/usr/bin/env python3
"""Patch Hermes gemini_schema.py so plow_send_message `to` does not 400 Gemini.

Idempotent. Usage: python3 patches/fix_gemini_schema.py [path]
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
HELPER_SRC = (HERE / "gemini_items.py").read_text(encoding="utf-8")
# Drop the module docstring / future import; keep the function body.
HELPER_FN = HELPER_SRC.split("from typing import Any, Dict\n", 1)[-1]
HELPER_FN = HELPER_FN.replace("def place_items_on_array_branches", "def _place_items_on_array_branches")

CALL = "    _place_items_on_array_branches(cleaned)\n"


def apply(path: Path) -> str:
    src = path.read_text(encoding="utf-8")
    if "_place_items_on_array_branches" in src:
        return "already patched"
    if "def sanitize_gemini_schema(" not in src:
        raise SystemExit(f"no sanitize_gemini_schema in {path}")
    src = src.replace(
        "def sanitize_gemini_schema(",
        HELPER_FN.lstrip("\n") + "\n\ndef sanitize_gemini_schema(",
        1,
    )
    needle = '            cleaned["required"] = valid_required\n    return cleaned'
    alt = "            cleaned['required'] = valid_required\n    return cleaned"
    if needle in src:
        src = src.replace(needle, needle.replace("    return cleaned", CALL + "    return cleaned"), 1)
    elif alt in src:
        src = src.replace(alt, alt.replace("    return cleaned", CALL + "    return cleaned"), 1)
    else:
        raise SystemExit("return cleaned anchor not found")
    path.write_text(src, encoding="utf-8")
    return "patched"


def main() -> int:
    path = Path(sys.argv[1] if len(sys.argv) > 1 else "/opt/hermes/agent/gemini_schema.py")
    print(f"{path}: {apply(path)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
