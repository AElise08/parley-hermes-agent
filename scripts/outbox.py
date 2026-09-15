#!/usr/bin/env python3
"""Queue Plow Chat messages for now vs later.

The live gateway cannot deliver cron `--deliver plow_chat`. Jobs write here;
`drain` POSTs due items via send_chat.py and fires the daily practice nudge
inside the owner's local window.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from tutor_config import (
    load_settings,
    practice_hour,
    practice_window_minutes,
    timezone_name,
    zone,
)
from send_chat import hermes_home, send

OUTBOX = "outbox.jsonl"


def outbox_path() -> Path:
    path = hermes_home() / ".parley" / OUTBOX
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def parse_when(value: str) -> datetime:
    raw = (value or "now").strip().lower()
    now = datetime.now(zone())
    if raw in ("now", "agora"):
        return now
    try:
        if "T" in value or "+" in value or value.endswith("Z"):
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        else:
            parsed = datetime.fromisoformat(value)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=zone())
        return parsed
    except ValueError as exc:
        raise SystemExit(f"invalid --at timestamp: {value}") from exc


def load_items() -> list[dict]:
    path = outbox_path()
    if not path.exists():
        return []
    items = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        items.append(json.loads(line))
    return items


def save_items(items: list[dict]) -> None:
    path = outbox_path()
    payload = "".join(json.dumps(item, ensure_ascii=False) + "\n" for item in items)
    path.write_text(payload, encoding="utf-8")


def add(args: argparse.Namespace) -> dict:
    text = args.text
    if args.file:
        text = sys.stdin.read() if args.file == "-" else Path(args.file).read_text(encoding="utf-8")
    text = (text or "").strip()
    if not text:
        raise SystemExit("empty message")
    send_at = parse_when(args.at)
    item = {
        "id": datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f"),
        "send_at": send_at.isoformat(),
        "text": text,
        "reason": args.reason or "",
        "sent": False,
    }
    items = load_items()
    items.append(item)
    save_items(items)
    if send_at <= datetime.now(zone()):
        send(text)
        item["sent"] = True
        save_items(items)
        return {"queued": False, "sent": True, "item": {k: item[k] for k in ("id", "send_at", "reason")}}
    return {"queued": True, "sent": False, "item": {k: item[k] for k in ("id", "send_at", "reason")}}


def daily_stamp_path() -> Path:
    return hermes_home() / ".parley" / "daily-practice-last.txt"


def daily_window(now: datetime) -> bool:
    settings = load_settings()
    return (
        now.hour == practice_hour(settings)
        and now.minute < practice_window_minutes(settings)
    )


def run_daily_practice(force: bool = False) -> dict:
    settings = load_settings()
    now = datetime.now(zone(settings))
    stamp = daily_stamp_path()
    day = now.date().isoformat()
    if not force:
        if not daily_window(now):
            return {
                "daily": "skipped",
                "reason": (
                    f"not {practice_hour(settings):02d}h "
                    f"{timezone_name(settings)}"
                ),
            }
        if stamp.exists() and stamp.read_text(encoding="utf-8").strip() == day:
            return {"daily": "skipped", "reason": "already sent today"}
    import daily_practice
    code = daily_practice.main()
    if code == 0:
        stamp.write_text(day + "\n", encoding="utf-8")
    return {"daily": "sent" if code == 0 else "failed", "code": code}


def drain() -> dict:
    now = datetime.now(zone())
    items = load_items()
    sent_ids = []
    errors = []
    for item in items:
        if item.get("sent"):
            continue
        try:
            due = datetime.fromisoformat(item["send_at"])
            if due.tzinfo is None:
                due = due.replace(tzinfo=zone())
        except (KeyError, ValueError):
            continue
        if due > now:
            continue
        try:
            send(item.get("text") or "")
            item["sent"] = True
            item["sent_at"] = now.isoformat()
            sent_ids.append(item.get("id"))
        except SystemExit as exc:
            errors.append(str(exc))
            break
    save_items(items[-50:])
    pending = sum(1 for item in items if not item.get("sent"))
    result = {"sent": len(sent_ids), "pending": pending, "errors": errors}
    result.update(run_daily_practice(force=False))
    return result


def show() -> dict:
    items = load_items()
    pending = [item for item in items if not item.get("sent")]
    return {
        "pending": [
            {"id": i.get("id"), "send_at": i.get("send_at"), "reason": i.get("reason"), "preview": (i.get("text") or "")[:80]}
            for i in pending
        ]
    }


def main() -> int:
    if len(sys.argv) == 1:
        sys.argv.append("drain")
    p = argparse.ArgumentParser(description="Queue or drain Plow Chat messages.")
    sub = p.add_subparsers(dest="command", required=True)
    add_p = sub.add_parser("add")
    add_p.add_argument("--at", default="now", help="ISO local time, or 'now'")
    add_p.add_argument("--text", default="")
    add_p.add_argument("--file")
    add_p.add_argument("--reason", default="")
    sub.add_parser("drain")
    sub.add_parser("show")
    sub.add_parser("daily", help="Send the daily practice nudge now (test/force)")
    args = p.parse_args()
    if args.command == "add":
        result = add(args)
    elif args.command == "drain":
        result = drain()
    elif args.command == "daily":
        result = run_daily_practice(force=True)
    else:
        result = show()
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
