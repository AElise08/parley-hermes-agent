#!/usr/bin/env python3
"""Parley tutor state: profile, sessions, mistakes, spaced review.

One owner, one machine. The profile says which language they are learning and
where they are; the mistakes log is what the daily review is built from.
Nothing here invents corrections — the agent writes them in from the live
conversation, this script only stores, schedules, and formats.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

from send_chat import hermes_home
from tutor_config import LEVELS, load_settings, timezone_name, zone, normalize_locale

PROFILE_NAME = "tutor-profile.json"
STATE_DIR = ".parley"
SESSIONS_NAME = "sessions.jsonl"
ERRORS_NAME = "errors.json"

# Spaced-review ladder in days. Streak 0 is due again tomorrow; a streak past
# the top of the ladder stays at a month.
REVIEW_LADDER_DAYS = [1, 3, 7, 14, 30]

ERROR_KINDS = ["grammar", "vocab", "word-order", "register", "spelling", "pronunciation"]


# ---------- profile ----------

def profile_path() -> Path:
    return Path(os.environ.get("TUTOR_PROFILE", str(hermes_home() / PROFILE_NAME)))


def load_profile() -> dict:
    path = profile_path()
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def save_profile(profile: dict) -> None:
    path = profile_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(profile, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def state_dir() -> Path:
    path = hermes_home() / STATE_DIR
    path.mkdir(parents=True, exist_ok=True)
    return path


def now_local() -> datetime:
    return datetime.now(zone())


def setup_status() -> dict:
    profile = load_profile()
    target = str(profile.get("target_language") or "").strip()
    native = str(profile.get("native_language") or "").strip()
    level = str(profile.get("level") or "").strip()
    ready = bool(target and native and level)
    if ready:
        next_step = (
            f"Profile is ready: {native} speaker learning {target} at {level}. "
            "Chat, correct, and log mistakes from the conversation."
        )
    elif target and native:
        next_step = (
            "Languages are set but level is not. Run a short placement chat, "
            "then profile set --level A1..C2 with the estimate."
        )
    else:
        next_step = (
            "Match this message's language (voice: the [lang:xx] tag — en, de, "
            "es, ja, pt, fr, any Whisper code) and ask in that language which "
            "one they want to learn. Then setup-local / profile set with THEIR "
            "answer. Do not assume Portuguese or French."
        )
    return {
        "ready": ready,
        "target_language": target,
        "native_language": native,
        "level": level,
        "topics": profile.get("topics") or [],
        "goal": str(profile.get("goal") or ""),
        "profile_path": str(profile_path()),
        "next": next_step,
    }


def setup_local(_args: argparse.Namespace | None = None) -> dict:
    profile = load_profile()
    profile.setdefault("target_language", "")
    profile.setdefault("native_language", "")
    profile.setdefault("level", "")
    profile.setdefault("level_history", [])
    profile.setdefault("goal", "")
    profile.setdefault("topics", [])
    save_profile(profile)
    sessions = state_dir() / SESSIONS_NAME
    sessions.touch(exist_ok=True)
    errors = state_dir() / ERRORS_NAME
    if not errors.exists():
        save_errors([])
    return {
        "ok": True,
        "profile_path": str(profile_path()),
        "state_dir": str(state_dir()),
    }


def profile_show() -> dict:
    profile = load_profile()
    return {"profile": profile, "profile_path": str(profile_path())}


def profile_set(args: argparse.Namespace) -> dict:
    profile = load_profile()
    changed = {}
    for key, value in (
        ("target_language", args.target),
        ("native_language", args.native),
        ("goal", args.goal),
    ):
        if value is not None:
            stripped = value.strip()
            if key in ("target_language", "native_language"):
                stripped = normalize_locale(stripped) or stripped.lower()[:2]
            profile[key] = stripped
            changed[key] = profile[key]
    if args.topics is not None:
        topics = [t.strip() for t in args.topics.split(",") if t.strip()]
        profile["topics"] = topics
        changed["topics"] = topics
    if args.level is not None:
        return {"error": "use level set --level ... --reason ... so the change is recorded"}
    save_profile(profile)
    return {"ok": True, "changed": changed}


def level_set(args: argparse.Namespace) -> dict:
    level = args.level.strip().upper()
    if level not in LEVELS:
        return {"error": f"level must be one of {', '.join(LEVELS)}"}
    profile = load_profile()
    previous = str(profile.get("level") or "")
    history = profile.get("level_history") or []
    history.append({
        "ts": now_local().isoformat(timespec="seconds"),
        "from": previous,
        "to": level,
        "reason": (args.reason or "").strip(),
    })
    profile["level_history"] = history
    profile["level"] = level
    save_profile(profile)
    return {"ok": True, "from": previous, "to": level, "entries": len(history)}


# ---------- sessions ----------

def sessions_path() -> Path:
    return state_dir() / SESSIONS_NAME


def load_sessions() -> list[dict]:
    path = sessions_path()
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows


def session_log(args: argparse.Namespace) -> dict:
    role = args.role.strip().lower()
    if role not in ("owner", "tutor"):
        return {"error": "role must be owner or tutor"}
    text = (args.text or "").strip()
    if not text:
        return {"error": "empty text"}
    row = {"ts": now_local().isoformat(timespec="seconds"), "role": role, "text": text}
    with sessions_path().open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    return {"ok": True, "logged": role}


def session_note(args: argparse.Namespace) -> dict:
    summary = (args.summary or "").strip()
    if not summary:
        return {"error": "empty summary"}
    row = {
        "ts": now_local().isoformat(timespec="seconds"),
        "role": "note",
        "text": summary,
        "level": str(load_profile().get("level") or ""),
    }
    with sessions_path().open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    return {"ok": True}


def session_tail(args: argparse.Namespace) -> dict:
    rows = load_sessions()
    return {"count": len(rows), "tail": rows[-args.limit:]}


def practice_streak(sessions: list[dict] | None = None) -> dict:
    sessions = sessions if sessions is not None else load_sessions()
    owner_days = sorted({
        row["ts"][:10] for row in sessions
        if row.get("role") == "owner" and str(row.get("ts", ""))[:10]
    }, reverse=True)
    if not owner_days:
        return {"streak_days": 0, "last_practice": "", "total_days": 0}
    today = now_local().date()
    streak = 0
    cursor = today
    days = set(owner_days)
    # A streak survives not having practiced yet today.
    if cursor.isoformat() not in days:
        cursor = cursor - timedelta(days=1)
    while cursor.isoformat() in days:
        streak += 1
        cursor = cursor - timedelta(days=1)
    return {"streak_days": streak, "last_practice": owner_days[0], "total_days": len(days)}


# ---------- mistakes / review ----------

def errors_path() -> Path:
    return state_dir() / ERRORS_NAME


def load_errors() -> list[dict]:
    path = errors_path()
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    return data if isinstance(data, list) else []


def save_errors(items: list[dict]) -> None:
    errors_path().write_text(json.dumps(items, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def error_add(args: argparse.Namespace) -> dict:
    wrong = (args.wrong or "").strip()
    better = (args.better or "").strip()
    if not wrong or not better:
        return {"error": "both --wrong and --better are required"}
    kind = (args.kind or "grammar").strip().lower()
    if kind not in ERROR_KINDS:
        kind = "grammar"
    items = load_errors()
    # One open entry per (wrong, better): re-seeing the same mistake refreshes
    # it instead of duplicating the queue.
    now = now_local()
    for item in items:
        if item.get("wrong") == wrong and item.get("better") == better:
            item["seen_count"] = int(item.get("seen_count", 1)) + 1
            item["last_seen"] = now.isoformat(timespec="seconds")
            item["streak"] = 0
            item["next_due"] = now.isoformat(timespec="seconds")
            save_errors(items)
            return {"ok": True, "id": item["id"], "merged": True, "seen_count": item["seen_count"]}
    seq = max([int(i.get("seq", 0)) for i in items] or [0]) + 1
    item = {
        "id": f"err-{seq:04d}",
        "seq": seq,
        "ts": now.isoformat(timespec="seconds"),
        "last_seen": now.isoformat(timespec="seconds"),
        "kind": kind,
        "wrong": wrong,
        "better": better,
        "note": (args.note or "").strip(),
        "level_at_time": str(load_profile().get("level") or ""),
        "seen_count": 1,
        "streak": 0,
        "next_due": now.isoformat(timespec="seconds"),
        "reviews": [],
    }
    items.append(item)
    save_errors(items)
    return {"ok": True, "id": item["id"], "merged": False}


def due_errors(now: datetime | None = None) -> list[dict]:
    now = now or now_local()
    due = []
    for item in load_errors():
        try:
            when = datetime.fromisoformat(item.get("next_due", ""))
        except ValueError:
            continue
        if when.tzinfo is None:
            when = when.replace(tzinfo=zone())
        if when <= now:
            due.append(item)
    due.sort(key=lambda i: (i.get("next_due", ""), i.get("seq", 0)))
    return due


def error_list(args: argparse.Namespace) -> dict:
    items = load_errors()
    if not args.all:
        items = [i for i in items if int(i.get("streak", 0)) < len(REVIEW_LADDER_DAYS) - 1]
    return {"count": len(items), "errors": [
        {k: i.get(k) for k in ("id", "kind", "wrong", "better", "note", "streak", "next_due", "seen_count")}
        for i in items
    ]}


def review(args: argparse.Namespace) -> dict:
    due = due_errors()[: args.limit]
    return {
        "due": len(due_errors()),
        "review": [
            {
                "id": i["id"],
                "kind": i.get("kind"),
                "prompt": i.get("wrong"),
                "expected": i.get("better"),
                "note": i.get("note"),
                "streak": i.get("streak", 0),
            }
            for i in due
        ],
    }


def review_grade(args: argparse.Namespace) -> dict:
    items = load_errors()
    for item in items:
        if item.get("id") == args.id:
            result = args.result.strip().lower()
            if result not in ("good", "bad"):
                return {"error": "result must be good or bad"}
            now = now_local()
            if result == "good":
                item["streak"] = int(item.get("streak", 0)) + 1
            else:
                item["streak"] = 0
            rung = min(int(item.get("streak", 0)), len(REVIEW_LADDER_DAYS) - 1)
            item["next_due"] = (now + timedelta(days=REVIEW_LADDER_DAYS[rung])).isoformat(timespec="seconds")
            reviews = item.get("reviews") or []
            reviews.append({"ts": now.isoformat(timespec="seconds"), "result": result})
            item["reviews"] = reviews
            save_errors(items)
            return {
                "ok": True,
                "id": item["id"],
                "streak": item["streak"],
                "next_due": item["next_due"],
                "graduated": int(item.get("streak", 0)) >= len(REVIEW_LADDER_DAYS) - 1,
            }
    return {"error": f"no error with id {args.id}"}


# ---------- daily prompt ----------

def digest_prompt(_args: argparse.Namespace | None = None) -> dict:
    profile = load_profile()
    topics = profile.get("topics") or []
    sessions = load_sessions()
    # Rotate topics by how many days the owner has practiced, so the daily
    # starter does not hammer the first topic forever.
    topic = ""
    if topics:
        streak = practice_streak(sessions)
        topic = topics[streak["total_days"] % len(topics)]
    due = due_errors()
    review_item = None
    if due:
        top = due[0]
        review_item = {"id": top["id"], "kind": top.get("kind"), "prompt": top.get("wrong"), "expected": top.get("better")}
    return {
        "ready": bool(profile.get("target_language") and profile.get("native_language") and profile.get("level")),
        "target_language": profile.get("target_language") or "",
        "native_language": profile.get("native_language") or "",
        "level": profile.get("level") or "",
        "topic": topic,
        "topics": topics,
        "goal": profile.get("goal") or "",
        "review_item": review_item,
        "due_count": len(due),
        "streak": practice_streak(sessions),
        "timezone": timezone_name(load_settings()),
    }


def stats(_args: argparse.Namespace | None = None) -> dict:
    profile = load_profile()
    sessions = load_sessions()
    errors = load_errors()
    graduated = [e for e in errors if int(e.get("streak", 0)) >= len(REVIEW_LADDER_DAYS) - 1]
    return {
        "level": profile.get("level") or "",
        "level_changes": len(profile.get("level_history") or []),
        "sessions_turns": sum(1 for s in sessions if s.get("role") in ("owner", "tutor")),
        "mistakes_logged": len(errors),
        "mistakes_graduated": len(graduated),
        "due_now": len(due_errors()),
        "streak": practice_streak(sessions),
    }


def doctor() -> dict:
    status = setup_status()
    return {
        "profile_path": str(profile_path()),
        "state_dir": str(state_dir()),
        "ready": status["ready"],
        "settings": load_settings(),
        "stats": stats(),
    }


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Parley tutor state: profile, sessions, mistakes, review.")
    sub = p.add_subparsers(dest="command", required=True)

    sub.add_parser("setup-status")
    sub.add_parser("setup-local")

    pp = sub.add_parser("profile")
    psub = pp.add_subparsers(dest="profile_command", required=True)
    psub.add_parser("show")
    pset = psub.add_parser("set")
    pset.add_argument("--target")
    pset.add_argument("--native")
    pset.add_argument("--goal")
    pset.add_argument("--topics", help="comma-separated interest topics")
    pset.add_argument("--level", help="rejected here; use level set")

    lp = sub.add_parser("level")
    lsub = lp.add_subparsers(dest="level_command", required=True)
    lset = lsub.add_parser("set")
    lset.add_argument("--level", required=True)
    lset.add_argument("--reason", default="")

    sp = sub.add_parser("session")
    ssub = sp.add_subparsers(dest="session_command", required=True)
    slog = ssub.add_parser("log")
    slog.add_argument("--role", required=True, help="owner or tutor")
    slog.add_argument("--text", required=True)
    snote = ssub.add_parser("note")
    snote.add_argument("--summary", required=True)
    stail = ssub.add_parser("tail")
    stail.add_argument("--limit", type=int, default=10)

    ep = sub.add_parser("error")
    esub = ep.add_subparsers(dest="error_command", required=True)
    eadd = esub.add_parser("add")
    eadd.add_argument("--wrong", required=True)
    eadd.add_argument("--better", required=True)
    eadd.add_argument("--note", default="")
    eadd.add_argument("--kind", default="grammar")
    elist = esub.add_parser("list")
    elist.add_argument("--all", action="store_true")

    rp = sub.add_parser("review")
    rsub = rp.add_subparsers(dest="review_command")
    rlist = rsub.add_parser("due")
    rlist.add_argument("--limit", type=int, default=5)
    rgrade = rsub.add_parser("grade")
    rgrade.add_argument("--id", required=True)
    rgrade.add_argument("--result", required=True, help="good or bad")

    sub.add_parser("digest-prompt")
    sub.add_parser("stats")
    sub.add_parser("doctor")
    return p


def main() -> int:
    args = parser().parse_args()
    cmd = args.command
    if cmd == "setup-status":
        result = setup_status()
    elif cmd == "setup-local":
        result = setup_local()
    elif cmd == "profile":
        result = profile_show() if args.profile_command == "show" else profile_set(args)
    elif cmd == "level":
        result = level_set(args)
    elif cmd == "session":
        if args.session_command == "log":
            result = session_log(args)
        elif args.session_command == "note":
            result = session_note(args)
        else:
            result = session_tail(args)
    elif cmd == "error":
        result = error_add(args) if args.error_command == "add" else error_list(args)
    elif cmd == "review":
        if args.review_command == "grade":
            result = review_grade(args)
        else:
            result = review(args)
    elif cmd == "digest-prompt":
        result = digest_prompt()
    elif cmd == "stats":
        result = stats()
    else:
        result = doctor()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 1 if isinstance(result, dict) and "error" in result else 0


if __name__ == "__main__":
    raise SystemExit(main())
