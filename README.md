# UCLA Seat Watcher

Checks UCLA's public Schedule of Classes every 5 minutes (GitHub Actions) and sends a
phone push notification via [ntfy](https://ntfy.sh) when a class's enrollment status changes,
with an urgent alert when a seat opens up. It only notifies; you still enroll yourself in MyUCLA.

## How it runs
Each GitHub Actions run stays alive for ~5.5 hours, checking every 5 minutes, then starts the
next run itself. GitHub's scheduler is only a backup (it's unreliable for frequent jobs).
Queued/cancelled backup runs in the Actions tab are normal. Only one watcher runs at a time.

**To stop it:** Actions tab -> "Watch UCLA seats" -> "..." -> **Disable workflow**
(or `gh workflow disable watch.yml`). Re-enable and run it to start again.

## Notifications
Install the **ntfy** app (iOS / Android), tap **+**, and subscribe to the topic stored in the
repo secret `NTFY_TOPIC`. Keep the topic private: anyone who knows it can read and post to it.

You'll get:
- **Now watching** – once, when a course is first added
- **SEAT OPEN** (urgent) – status becomes Open, or the waitlist has free spots
- **Status changed** – any other change (e.g. enrollment cap changed)
- **Can't read** – 3 failed checks in a row (page layout changed or site down)
- **Still running** – weekly heartbeat

## Adding a course
1. Find the class at https://sa.ucla.edu/ro/public/soc and open its section's detail page
   (click the section link, e.g. "Lec 1").
2. Add its URL to `courses.json` with a name, then commit and push.

## Run locally
```
NTFY_TOPIC=your-topic python3 watch.py
```
