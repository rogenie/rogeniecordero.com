#!/usr/bin/env python3
"""
collect_articles.py - builds 9nthdimension/articles.json for the all-brands dashboard
at rogeniecordero.com/9nthdimension.

Usage:  python3 _hub/collect_articles.py <dir with the site repos cloned side by side>

Read-only on every site repo. Expects these clones (depth 1 is fine) in <dir>:
  9nthdimension-site, aetasliveforever-site, tibimundum-calendar, computatio-site,
  bookbyte-site, puroge-site, pinoy-mobile-mechanic
A repo that is missing is reported as a problem instead of crashing.

Statuses written per article: published | queued | due_today | missed | held
"missed" = scheduled before today (Pacific) and not live and not held.
"""
import json, re, sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

PT = ZoneInfo("America/Los_Angeles")
NOW = datetime.now(PT)
TODAY = NOW.date()
SRC = Path(sys.argv[1] if len(sys.argv) > 1 else ".")
OUT = Path(__file__).resolve().parents[1] / "9nthdimension" / "articles.json"
QUEUE_SHOW = 12          # upcoming items kept per stream
PUBLISHED_SHOW = 15      # most recent live items kept per stream


def d(s):
    return date.fromisoformat(str(s)[:10])


def calendar_stream(brand, label, repo, path, site, url_key=("url",), title_key="title", run_hour=7):
    """Streams driven by a calendar.json with date/status/url items."""
    f = SRC / repo / path
    if not f.exists():
        return {"brand": brand, "stream": label, "error": f"{repo}/{path} not found"}
    c = json.loads(f.read_text())
    items = c if isinstance(c, list) else next(v for v in c.values() if isinstance(v, list))
    cadence = c.get("cadence", "") if isinstance(c, dict) else ""
    out = []
    for i in items:
        dt = d(i["date"])
        title = i.get(title_key) or i.get("question") or i.get("title") or i.get("slug")
        url = i.get("url")
        if not url and i.get("path"):
            url = site.rstrip("/") + i["path"]
        st = i.get("status", "todo")
        if st == "published":
            s = "published"
        elif st == "held":
            s = "held"
        elif dt < TODAY:
            s = "missed"
        elif dt == TODAY:
            s = "missed" if NOW.hour >= run_hour + 3 else "due_today"
        else:
            s = "queued"
        out.append({"date": i["date"][:10], "title": title, "status": s,
                    "url": url if s == "published" else None,
                    "note": i.get("note") or i.get("held_reason")})
    return {"brand": brand, "stream": label, "cadence": cadence, "items": out}


def frontmatter_date(text):
    m = re.search(r"^date:\s*['\"]?(\d{4}-\d{2}-\d{2})", text, re.M)
    return m.group(1) if m else None


def nine_dimension():
    repo = SRC / "9nthdimension-site"
    if not repo.exists():
        return {"brand": "9nth Dimension", "stream": "Articles", "error": "9nthdimension-site not found"}
    out = []
    pub_dates = set()
    for f in sorted((repo / "content" / "articles").glob("*.md")):
        t = f.read_text()
        dt = frontmatter_date(t)
        m = re.search(r"^title:\s*(.+)$", t, re.M)
        rung = re.search(r"^rung:\s*(\S+)", t, re.M)
        slug = f.stem
        url = f"https://9nthdimension.com/ladder/{rung.group(1)}/{slug}/" if rung else "https://9nthdimension.com/"
        out.append({"date": dt, "title": m.group(1).strip().strip('"') if m else slug,
                    "status": "published", "url": url})
        if dt:
            pub_dates.add(d(dt))
    # Publisher runs on odd days of the month (cron */2), one article per run.
    start = min(pub_dates) if pub_dates else TODAY
    day = start
    while day < TODAY or (day == TODAY and NOW.hour >= 9):
        if day.day % 2 == 1 and day not in pub_dates:
            out.append({"date": day.isoformat(), "title": "No article went live on this scheduled day",
                        "status": "missed", "url": None, "slot": True})
        day += timedelta(days=1)
    # Queue: backlog todo entries, projected onto the next odd days.
    backlog = (repo / "content" / "backlog.yml").read_text()
    todo = re.findall(r'^- \{q: "(.+?)",.*status: todo', backlog, re.M)
    nxt = TODAY if (TODAY.day % 2 == 1 and NOW.hour < 6 and TODAY not in pub_dates) else TODAY + timedelta(days=1)
    for q in todo:
        while nxt.day % 2 == 0:
            nxt += timedelta(days=1)
        out.append({"date": nxt.isoformat(), "title": q, "status": "queued", "url": None})
        nxt += timedelta(days=1)
    return {"brand": "9nth Dimension", "stream": "Articles", "cadence": "Odd days of the month, 5:37 AM Pacific", "items": out}


def pinoy():
    repo = SRC / "pinoy-mobile-mechanic"
    if not repo.exists():
        return {"brand": "Pinoy Mobile Mechanic", "stream": "Blog", "error": "pinoy-mobile-mechanic not found"}
    out, dates = [], set()
    st = json.loads((repo / "status.json").read_text()) if (repo / "status.json").exists() else {}
    for a in st.get("articles", []):
        out.append({"date": a["date"], "title": a["title"], "status": "published", "url": a.get("url")})
        dates.add(d(a["date"]))
    if not out:
        for f in sorted((repo / "content" / "articles").glob("*.md")):
            dt = f.name[:10]
            out.append({"date": dt, "title": f.stem[11:].replace("-", " "), "status": "published", "url": None})
            dates.add(d(dt))
    # Runs on even days; it skips a day when an article is dated that day or the day before.
    start = min(dates) if dates else TODAY
    day = start
    while day < TODAY or (day == TODAY and NOW.hour >= 8):
        if day.day % 2 == 0 and day not in dates and (day - timedelta(days=1)) not in dates:
            out.append({"date": day.isoformat(), "title": "No article went live on this scheduled day",
                        "status": "missed", "url": None, "slot": True})
        day += timedelta(days=1)
    kw = (repo / "content" / "keywords.md").read_text()
    todo = re.findall(r"^- \[ \] [^|]+\|\s*([^|]+?)\s*\|", kw, re.M)
    nxt = TODAY + timedelta(days=1)
    for k in todo:
        while nxt.day % 2 == 1:
            nxt += timedelta(days=1)
        out.append({"date": nxt.isoformat(), "title": k, "status": "queued", "url": None})
        nxt += timedelta(days=1)
    return {"brand": "Pinoy Mobile Mechanic", "stream": "Blog", "cadence": "Even days of the month, 4:53 AM Pacific", "items": out}


MONTHS = {m: i for i, m in enumerate(["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"], 1)}


def astro(brand, repo, site, cal=None):
    r = SRC / repo
    if not r.exists():
        return {"brand": brand, "stream": "Articles", "error": f"{repo} not found"}
    out, dates = [], set()
    for f in sorted((r / "src/content/articles").glob("*.md*")):
        t = f.read_text()
        if re.search(r"^draft:\s*true", t, re.M):
            continue
        dt = re.search(r"^publishDate:\s*['\"]?(\d{4}-\d{2}-\d{2})", t, re.M)
        ti = re.search(r"^title:\s*(.+)$", t, re.M)
        sl = re.search(r"^slug:\s*(\S+)", t, re.M)
        slug = sl.group(1) if sl else f.stem
        out.append({"date": dt.group(1) if dt else None, "title": ti.group(1).strip().strip('"') if ti else slug,
                    "status": "published", "url": f"{site}/articles/{slug}/"})
        if dt:
            dates.add(dt.group(1))
    cadence = "No publishing calendar yet"
    if cal and (r / cal).exists():
        cadence = "Mon, Wed, Fri (docs/content-calendar.md)"
        for m in re.finditer(r"^\|\s*\w{3}\s+(\d{1,2})\s+(\w{3})\s+(\d{4})\s*\|\s*([^|]+?)\s*\|", (r / cal).read_text(), re.M):
            dt = date(int(m.group(3)), MONTHS[m.group(2)], int(m.group(1))).isoformat()
            if dt in dates:
                continue
            st = "missed" if d(dt) < TODAY else "due_today" if d(dt) == TODAY else "queued"
            out.append({"date": dt, "title": m.group(4), "status": st, "url": None,
                        "note": "No publisher is scheduled for this site" if st == "missed" else None})
    return {"brand": brand, "stream": "Articles", "cadence": cadence, "items": out}


MONTH_NAMES = ["January","February","March","April","May","June","July","August","September","October","November","December"]


def natal():
    r = SRC / "natalnotes-site"
    site = "https://mynatalnotes.com"
    if not r.exists():
        return {"brand": "Natal Notes", "stream": "Website", "error": "natalnotes-site not found"}
    def path(k, slug, month, sign):
        mm = f"{MONTH_NAMES[int(month[5:7]) - 1].lower()}-{month[:4]}" if month else ""
        return f"/sidereal-horoscope/{sign}/{mm}/" if k == "forecast" else f"/vedic-astrology/{mm}/" if k == "overview" else f"/guides/{slug}/"
    out, seen = [], set()
    for f in sorted((r / "content/posts").glob("*.md")):
        t = f.read_text()
        g = lambda k: (re.search(rf"^{k}:\s*[\"']?([^\"'\n]+)", t, re.M) or [None, ""])[1].strip()
        url = site + path(g("kind"), g("slug"), g("month"), g("sign"))
        seen.add(url)
        out.append({"date": g("date"), "title": g("title"), "status": "published", "url": url})
    for line in (r / "content/calendar.yml").read_text().splitlines():
        if not line.startswith("- {"):
            continue
        g = lambda k: (re.search(rf"[{{ ]{k}: ([^,}}]+)", line) or [None, ""])[1].strip()
        if g("status") == "published":
            continue
        k, on, slug, month, sign = g("kind"), g("date") or g("on"), g("slug"), g("month"), g("sign")
        if site + path(k, slug, month, sign) in seen:
            continue
        mname = f"{MONTH_NAMES[int(month[5:7]) - 1]} {month[:4]}" if month else ""
        title = f"{sign.capitalize()} sidereal horoscope, {mname}" if k == "forecast" else f"Vedic astrology {mname}: monthly overview" if k == "overview" else slug.replace("-", " ").capitalize()
        st = "missed" if d(on) < TODAY else ("missed" if NOW.hour >= 9 else "due_today") if d(on) == TODAY else "queued"
        out.append({"date": on, "title": title, "status": st, "url": None,
                    "note": "Overdue: the next run publishes it and the rest slide" if st == "missed" else None})
    return {"brand": "Natal Notes", "stream": "Website", "cadence": "One post every other day (content/calendar.yml)", "items": out}


def trim(stream):
    if "items" not in stream:
        return stream
    items = sorted(stream["items"], key=lambda i: (i["date"] or ""))
    pub = [i for i in items if i["status"] == "published"]
    q = [i for i in items if i["status"] in ("queued", "due_today")]
    bad = [i for i in items if i["status"] in ("missed", "held")]
    stream["counts"] = {"published": len(pub), "queued": len(q), "missed": sum(i["status"] == "missed" for i in bad),
                        "held": sum(i["status"] == "held" for i in bad),
                        "published_7d": sum(1 for i in pub if i["date"] and d(i["date"]) > TODAY - timedelta(days=7))}
    stream["published"] = list(reversed(pub))[:PUBLISHED_SHOW]
    stream["queue"] = q[:QUEUE_SHOW]
    stream["problems"] = bad
    stream["next"] = q[0] if q else None
    del stream["items"]
    return stream


streams = [
    nine_dimension(),
    calendar_stream("ÆTAS", "Articles", "aetasliveforever-site", "_src/calendar.json", "https://aetasliveforever.com", run_hour=6),
    calendar_stream("Tibi Mundum", "PTO guides", "tibimundum-calendar", "_guides/calendar.json", "https://tibimundum.com", run_hour=6),
    calendar_stream("Tibi Mundum", "Itineraries", "tibimundum-calendar", "_itineraries/calendar.json", "https://tibimundum.com", run_hour=6),
    calendar_stream("Computatio", "Answers", "computatio-site", "_src/answers_calendar.json", "https://computatio.io", title_key="question", run_hour=5),
    calendar_stream("BookByte", "Guides", "bookbyte-site", "_src/calendar.json", "https://bookbytellc.com", run_hour=6),
    calendar_stream("Purogé", "Journal", "puroge-site", "content/calendar.json", "https://puroge.com", run_hour=5),
    pinoy(),
    natal(),
    astro("Intelligentia Antiqua", "intelligentiaantiqua-site", "https://intelligentiaantiqua.com", "docs/content-calendar.md"),
    astro("Satsplain", "satsplain-site", "https://satsplain.com"),
]
# Computatio answers: fill live URLs from slugs (its calendar has no url field).
for s in streams:
    if s.get("brand") == "Computatio" and "items" in s:
        cal = json.loads((SRC / "computatio-site/_src/answers_calendar.json").read_text())["items"]
        by_date = {}
        for i in cal:
            by_date.setdefault(i["date"], []).append(i)
        for it in s["items"]:
            if it["status"] == "published" and not it["url"]:
                for i in by_date.get(it["date"], []):
                    if (i.get("question") == it["title"]) and i.get("slug"):
                        it["url"] = f"https://computatio.io/answers/{i['slug']}/"

data = {"generated": NOW.isoformat(timespec="minutes"), "today": TODAY.isoformat(),
        "streams": [trim(s) for s in streams]}
OUT.write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n")
print(f"wrote {OUT}")
for s in data["streams"]:
    if "error" in s:
        print(f"  {s['brand']} / {s['stream']}: ERROR {s['error']}")
    else:
        c = s["counts"]
        print(f"  {s['brand']} / {s['stream']}: {c['published']} live ({c['published_7d']} this week), {c['queued']} queued, {c['missed']} missed, {c['held']} held")
