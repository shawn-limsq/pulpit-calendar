#!/usr/bin/env python3
"""Build the pulpit-schedule calendar feed.

The full-year schedule in schedule/baseline/ supplies every date. Quarterly
files in schedule/quarterly/ (with chairpersons) override speaker, title and
chairperson for the dates they cover.

Supports .docx, .pdf, .xlsx and .csv. Columns are matched by their header
names, so a new format with extra columns (e.g. Chairperson) works as long as
the header row has recognisable names. Service times are set in SERVICE_TIMES
below; a service that matches no rule becomes an all-day event.

Usage: python build_calendar.py [baseline-file [quarterly-file ...]]
Output: docs/preaching.ics
"""
import csv
import hashlib
import re
import sys
from datetime import date, datetime, timedelta, timezone
from datetime import time as clock
from pathlib import Path

from icalendar import Calendar, Event

ROOT = Path(__file__).resolve().parent
SCHEDULE_DIR = ROOT / "schedule"
BASELINE_DIR = SCHEDULE_DIR / "baseline"    # full-year speaker schedule
QUARTERLY_DIR = SCHEDULE_DIR / "quarterly"  # quarterly files with chairpersons
OUT = ROOT / "docs" / "preaching.ics"
CAL_NAME = "LBPC Pulpit Schedule"
UID_DOMAIN = "pulpit.lifebpc.com"
EVENT_PREFIX = "LBPC Worship"
SGT = timezone(timedelta(hours=8))  # Singapore, no daylight saving

# Service times (Singapore time), checked in order against the sermon title
# (case-insensitive). The first rule whose keyword appears in the title wins.
# None means an all-day event (time not confirmed).
SERVICE_TIMES = [
    (("combined", "acm", "anniversary", "easter"), [(clock(9, 0), clock(10, 45))]),
    (("good friday",), [(clock(9, 0), clock(10, 45))]),
    (("watchnight",), [(clock(22, 30), clock(0, 0))]),   # ends at midnight
    (("christmas eve",), None),                          # time not confirmed
]
SUNDAY_TIMES = [(clock(8, 0), clock(9, 15)), (clock(11, 0), clock(12, 15))]


def service_times(svc):
    """List of (start, end) times for a service, or None for all-day."""
    title = " ".join(svc["title"].split()).lower()
    for keywords, times in SERVICE_TIMES:
        if any(k in title for k in keywords):
            return times
    return SUNDAY_TIMES if svc["date"].weekday() == 6 else None

# Quarterly sub-themes, by year. Q1 = Jan–Mar, Q2 = Apr–Jun, and so on.
# For a year not listed here, the quarter heading row in the schedule is used.
SUBTHEMES = {
    2027: [
        "Redeeming the Time Begins with a Heart of Wisdom",
        "Redeeming the Time by Living in God’s Presence",
        "Redeeming the Time by Making Wise Choices",
        "Redeeming the Time by Being Always Ready",
    ],
}


def subtheme_for(svc):
    year_themes = SUBTHEMES.get(svc["date"].year)
    if year_themes:
        return year_themes[(svc["date"].month - 1) // 3]
    return svc["series"].title() if svc["series"].isupper() else svc["series"]

# Header names (lower-case, substring match) -> field
COLUMN_ALIASES = {
    "date": ["date"],
    "text": ["text", "passage", "scripture", "reading"],
    "title": ["title", "sermon", "topic", "theme"],
    "speaker": ["speaker", "preacher"],
    "chair": ["chair", "presid", "worship leader", "liturgist"],
    "notes": ["notes", "remarks", "description"],
    "movement": ["movement", "events"],
}

SCRIPTURE_RE = re.compile(r"\b\d+\s*:\s*\d+")
DATE_FORMATS = ["%d %b %y", "%d %b %Y", "%d %B %y", "%d %B %Y", "%d/%m/%Y",
                "%d/%m/%y", "%Y-%m-%d", "%d-%b-%y", "%d-%b-%Y", "%d.%m.%Y"]


def clean(s):
    s = (s or "").replace(" ", " ")
    lines = [re.sub(r"\s+", " ", ln).strip() for ln in s.splitlines()]
    return "\n".join(ln for ln in lines if ln)


def clean_person(s):
    """Drop planning notes typed next to a name.

    "Rev Tan EB Confirmed!" -> "Rev Tan EB"; "Wei En Yi?" -> "Wei En Yi (TBC)".
    """
    s = " ".join(s.split())
    s = re.sub(r"\(?\b(?:not\s+(?:yet\s+)?confirmed|unconfirmed|tbc|tba|tbd|pending)\b\)?", "?", s, flags=re.I)
    s = re.sub(r"\(?\bconfirmed\b[!.]*\)?", "", s, flags=re.I)
    tentative = "?" in s
    s = " ".join(s.replace("?", " ").replace("!", " ").split()).strip(" -–,;")
    return f"{s} (TBC)" if tentative and s else s


def parse_date(s):
    s = re.sub(r"\(.*?\)", "", clean(s)).strip()
    s = re.sub(r"^(mon|tue|wed|thu|fri|sat|sun)\w*,?\s*", "", s, flags=re.I)
    s = re.sub(r"(\d)(st|nd|rd|th)\b", r"\1", s)
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            pass
    return None


# ---------- readers: each returns a list of rows (list of cell strings) ----------

def rows_from_docx(path):
    import docx
    rows = []
    for table in docx.Document(path).tables:
        for r in table.rows:
            rows.append([c.text for c in r.cells])
    return rows


def rows_from_pdf(path):
    import pdfplumber
    rows = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            for table in page.extract_tables():
                rows.extend([[c or "" for c in r] for r in table])
    return rows


def rows_from_xlsx(path):
    import openpyxl
    rows = []
    for ws in openpyxl.load_workbook(path, data_only=True).worksheets:
        for r in ws.iter_rows(values_only=True):
            rows.append([v.strftime("%d %b %Y") if isinstance(v, (datetime, date))
                         else ("" if v is None else str(v)) for v in r])
    return rows


def rows_from_csv(path):
    with open(path, newline="", encoding="utf-8-sig") as f:
        return list(csv.reader(f))


READERS = {".docx": rows_from_docx, ".pdf": rows_from_pdf,
           ".xlsx": rows_from_xlsx, ".csv": rows_from_csv}


# ---------- interpretation ----------

def map_header(row):
    cells = [clean(c).lower() for c in row]
    if not any(c == "date" or c.startswith("date") for c in cells):
        return None
    mapping = {}
    for i, c in enumerate(cells):
        for field, aliases in COLUMN_ALIASES.items():
            if field not in mapping and any(a in c for a in aliases):
                mapping[field] = i
                break
    return mapping if "date" in mapping else None


def extract_services(rows):
    services, colmap, series = [], None, ""
    for row in rows:
        header = map_header(row)
        if header:
            colmap = header
            continue
        if not colmap:
            continue
        get = lambda f: clean(row[colmap[f]]) if f in colmap and colmap[f] < len(row) else ""
        d = parse_date(get("date"))
        if not d:
            # A merged full-width row is a series / quarter heading
            vals = {clean(c) for c in row if clean(c)}
            if len(vals) == 1:
                series = vals.pop()
            continue
        svc = {f: get(f) for f in COLUMN_ALIASES if f != "date"}
        svc["speaker"] = clean_person(svc["speaker"])
        svc["chair"] = clean_person(svc["chair"])
        svc["date"], svc["series"] = d, series
        # Passage sometimes lands in Notes when Text is blank
        if not svc["text"] and SCRIPTURE_RE.search(svc["notes"]) and len(svc["notes"]) < 40:
            svc["text"], svc["notes"] = svc["notes"], ""
        services.append(svc)
    return services


def build_ics(services, source_name):
    cal = Calendar()
    cal.add("prodid", "-//LBPC//Pulpit Schedule//EN")
    cal.add("version", "2.0")
    cal.add("calscale", "GREGORIAN")
    cal.add("method", "PUBLISH")
    cal.add("x-wr-calname", CAL_NAME)
    cal.add("x-wr-caldesc", f"Pulpit schedule (source: {source_name}). Updates automatically.")
    cal.add("refresh-interval", timedelta(hours=1), parameters={"VALUE": "DURATION"})
    cal["x-published-ttl"] = "PT1H"

    stamp = datetime.now(timezone.utc).replace(microsecond=0)
    seen = {}
    for s in sorted(services, key=lambda s: s["date"]):
        n = seen.get(s["date"], 0)
        seen[s["date"]] = n + 1
        # UID depends only on the date (and order within the date), so edits
        # to speaker/title update the existing event instead of duplicating it.
        uid_key = s["date"].isoformat() + (f"-{n}" if n else "")
        uid = hashlib.sha1(uid_key.encode()).hexdigest()[:16] + "@" + UID_DOMAIN

        sermon = s["title"].replace("\n", " – ") or "TBA"
        summary = f"{EVENT_PREFIX}: {sermon}"
        # Inner brackets avoid nested parentheses: "(Lk 8:1-15 [cf Matt 13])"
        passage = " ".join(s["text"].split()).replace("(", "[").replace(")", "]")
        if passage:
            summary += f" ({passage})"

        desc = [
            f"Speaker: {s['speaker'] or 'TBA'}",
            f"Chairperson: {s['chair'] or 'Not confirmed'}",
        ]
        subtheme = subtheme_for(s)
        if subtheme:
            desc.append(f"Sub-theme: {subtheme}")

        times = service_times(s)
        slots = times or [None]
        for i, slot in enumerate(slots):
            ev = Event()
            # The first service of the day keeps the date-based UID, so
            # existing subscribers' events are updated rather than duplicated.
            ev.add("uid", uid if i == 0 else uid.replace("@", f"-{i + 1}@", 1))
            ev.add("dtstamp", stamp)
            if slot is None:
                ev.add("dtstart", s["date"])
                ev.add("dtend", s["date"] + timedelta(days=1))
            else:
                start = datetime.combine(s["date"], slot[0], SGT)
                end = datetime.combine(s["date"], slot[1], SGT)
                if end <= start:  # runs past midnight
                    end += timedelta(days=1)
                # Written in UTC so no time-zone block is needed in the feed
                ev.add("dtstart", start.astimezone(timezone.utc))
                ev.add("dtend", end.astimezone(timezone.utc))
            ev.add("summary", summary)
            ev.add("description", "\n".join(desc))
            ev.add("transp", "TRANSPARENT")  # doesn't mark you as busy
            cal.add_component(ev)
    return cal.to_ical()


def _changed_at(p):
    """Last commit time of the file (reliable on GitHub), else file mtime."""
    import subprocess
    try:
        out = subprocess.run(["git", "log", "-1", "--format=%ct", "--", str(p)],
                             cwd=ROOT, capture_output=True, text=True).stdout.strip()
        if out:
            return int(out)
    except OSError:
        pass
    return p.stat().st_mtime


VERSION_RE = re.compile(r"\bv(?:er(?:sion)?)?\.?\s*(\d+(?:\.\d+)*)", re.I)


def version_of(name):
    m = VERSION_RE.search(name)
    return tuple(int(x) for x in m.group(1).split(".")) if m else ()


def schedule_files(folder):
    if not folder.is_dir():
        return []
    return [p for p in folder.iterdir() if p.suffix.lower() in READERS]


def newest(files):
    """Highest version in the file name wins; ties go to the most recent upload."""
    return max(files, key=lambda p: (version_of(p.name), _changed_at(p)))


def read_services(path):
    services = extract_services(READERS[path.suffix.lower()](path))
    if not services:
        sys.exit(f"Found no dated rows in {path.name}; check the header row has a 'Date' column.")
    return services


def apply_quarterly(base, quarterly_files):
    """Quarterly files override the baseline for the dates they cover.

    For each date, only the newest quarterly file that lists it is used, so a
    revised Q1 file replaces the earlier Q1 file, while Q2 leaves Q1 alone.
    Speaker, title and chairperson from the quarterly file win; a blank cell
    keeps the baseline value. Dates missing from the baseline are added.
    """
    by_date = {}
    for s in base:
        by_date.setdefault(s["date"], s)
    claimed = set()
    ordered = sorted(quarterly_files, key=lambda p: (version_of(p.name), _changed_at(p)), reverse=True)
    for path in ordered:
        for q in read_services(path):
            if q["date"] in claimed:
                continue
            target = by_date.get(q["date"])
            if target is None:
                base.append(q)
                by_date[q["date"]] = q
            else:
                for field in ("speaker", "title", "chair"):
                    if q[field]:
                        target[field] = q[field]
            claimed.add(q["date"])
    return base


def main():
    if len(sys.argv) > 1:
        base_path, quarterly = Path(sys.argv[1]), [Path(a) for a in sys.argv[2:]]
    else:
        base_files = schedule_files(BASELINE_DIR)
        if not base_files:
            sys.exit("No full-year schedule found in schedule/baseline/")
        base_path, quarterly = newest(base_files), schedule_files(QUARTERLY_DIR)

    services = apply_quarterly(read_services(base_path), quarterly)
    sources = base_path.name + (f" + {len(quarterly)} quarterly file(s)" if quarterly else "")
    new = build_ics(services, base_path.name)
    strip = lambda b: re.sub(rb"DTSTAMP:[^\r\n]*", b"", b)
    if OUT.exists() and strip(OUT.read_bytes()) == strip(new):
        print(f"{len(services)} services from {sources}; no changes to the calendar.")
        return
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_bytes(new)
    print(f"{len(services)} services from {sources} -> {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
