#!/usr/bin/env python3
"""Watch UCLA Schedule of Classes pages and push a notification via ntfy.sh
when a class's enrollment status changes (e.g. "Closed: Class Full" -> "Open").

Standard library only. Config: courses.json. State: state.json.
Env: NTFY_TOPIC (required to send notifications; without it, prints only).
"""
import datetime as dt
import html
import json
import os
import re
import sys
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
COURSES_FILE = os.path.join(HERE, "courses.json")
STATE_FILE = os.path.join(HERE, "state.json")
UA = "Mozilla/5.0 (X11; Linux x86_64) ucla-seat-watcher"
ERROR_ALERT_AFTER = 3          # consecutive failed checks before alerting
HEARTBEAT_DAYS = 7             # "still watching" message (also keeps the repo active)


def fetch(url, retries=2):
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.read().decode("utf-8", errors="replace")
        except Exception:
            if attempt == retries:
                raise
            time.sleep(5)


def clean(fragment):
    text = re.sub(r"<[^>]+>", " ", fragment)
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def parse_status(page):
    """Return (status, waitlist) from the class-detail page's enrollment table."""
    table = re.search(r'id="enrl_mtng_info".*?<tbody>(.*?)</tbody>', page, re.S)
    if not table:
        raise ValueError("enrollment table not found (page layout may have changed)")
    cells = re.findall(r"<td[^>]*>(.*?)</td>", table.group(1), re.S)
    if len(cells) < 2:
        raise ValueError("enrollment row has too few cells")
    status, waitlist = clean(cells[0]), clean(cells[1])
    if not re.match(r"(Open|Closed|Waitlist|Cancel|Tenative|Tentative)", status, re.I):
        raise ValueError(f"unrecognized status text: {status!r}")
    return status, waitlist


def is_available(status, waitlist):
    if status.lower().startswith("open"):
        return True
    # Waitlist with free spots, e.g. "3 of 10 Taken"
    m = re.search(r"(\d+)\s+of\s+(\d+)\s+Taken", waitlist, re.I)
    return bool(m and int(m.group(1)) < int(m.group(2)))


def notify(title, message, priority="default", tags="", click=None):
    topic = os.environ.get("NTFY_TOPIC")
    print(f"[notify:{priority}] {title} | {message}")
    if not topic:
        return
    headers = {"Title": title, "Priority": priority, "Tags": tags}
    if click:
        headers["Click"] = click
    req = urllib.request.Request(
        f"https://ntfy.sh/{topic}", data=message.encode("utf-8"), headers=headers, method="POST"
    )
    urllib.request.urlopen(req, timeout=30).read()


def load_json(path, default):
    try:
        with open(path) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def main():
    courses = load_json(COURSES_FILE, [])
    state = load_json(STATE_FILE, {})
    courses_state = state.setdefault("courses", {})
    now = dt.datetime.now(dt.timezone.utc)
    summary = []

    for c in courses:
        name, url = c["name"], c["url"]
        prev = courses_state.get(name, {})
        try:
            status, waitlist = parse_status(fetch(url))
        except Exception as e:
            errors = prev.get("errors", 0) + 1
            prev["errors"] = errors
            courses_state[name] = prev
            print(f"ERROR {name}: {e}")
            if errors == ERROR_ALERT_AFTER:
                notify(f"Seat watcher can't read {name}", f"{e}\nCheck manually: {url}",
                       priority="high", tags="warning", click=url)
            continue

        avail = is_available(status, waitlist)
        summary.append(f"{name}: {status} / {waitlist}")
        print(f"OK {name}: {status} | {waitlist} | available={avail}")

        if prev.get("errors", 0) >= ERROR_ALERT_AFTER:
            notify(f"Seat watcher recovered: {name}", f"{status} / {waitlist}", tags="white_check_mark")

        changed = (prev.get("status"), prev.get("waitlist")) != (status, waitlist)
        if changed and "status" in prev:
            if avail:
                notify(f"SEAT OPEN: {name}",
                       f"{status} / {waitlist}\nEnroll now at my.ucla.edu",
                       priority="urgent", tags="rotating_light,tada", click=url)
            else:
                notify(f"Status changed: {name}",
                       f"{prev.get('status')} -> {status} / {waitlist}", tags="information_source", click=url)
        elif "status" not in prev:
            notify(f"Now watching: {name}", f"{status} / {waitlist}", priority="low", tags="eyes", click=url)

        courses_state[name] = {"status": status, "waitlist": waitlist, "errors": 0}

    # Weekly heartbeat so you know it's alive (and so the repo commits regularly)
    last_hb = state.get("last_heartbeat")
    if not last_hb or now - dt.datetime.fromisoformat(last_hb) >= dt.timedelta(days=HEARTBEAT_DAYS):
        if last_hb:
            notify("Seat watcher still running", "\n".join(summary) or "No courses read", priority="min", tags="heartbeat")
        state["last_heartbeat"] = now.isoformat(timespec="seconds")

    # Drop state for courses no longer in courses.json
    for k in list(courses_state):
        if k not in {c["name"] for c in courses}:
            del courses_state[k]

    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2, sort_keys=True)
        f.write("\n")


if __name__ == "__main__":
    sys.exit(main())
