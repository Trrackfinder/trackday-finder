from fastapi import FastAPI, Query
from fastapi.responses import HTMLResponse, Response
import requests
from bs4 import BeautifulSoup
import re
import time
import html
import calendar
from datetime import datetime, date, timedelta
from urllib.parse import urljoin, quote

app = FastAPI()

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "nl-NL,nl;q=0.9,en-US;q=0.8,en;q=0.7",
}

CACHE_SECONDS = 900
_cache = {"time": 0, "events": []}

MONTHS = {
    "jan": "01", "feb": "02", "mrt": "03", "mar": "03",
    "apr": "04", "mei": "05", "may": "05", "jun": "06",
    "jul": "07", "aug": "08", "sep": "09", "okt": "10",
    "oct": "10", "nov": "11", "dec": "12",
    "januari": "01", "februari": "02", "maart": "03",
    "april": "04", "juni": "06", "juli": "07",
    "augustus": "08", "september": "09", "oktober": "10",
    "november": "11", "december": "12",
}

DUTCH_MONTHS = [
    "", "januari", "februari", "maart", "april", "mei", "juni",
    "juli", "augustus", "september", "oktober", "november", "december"
]

CIRCUIT_ALIASES = {
    "spa-francorchamps": "Spa-Francorchamps",
    "spa francorchamps": "Spa-Francorchamps",
    "francorchamps": "Spa-Francorchamps",
    "circuit de spa": "Spa-Francorchamps",
    "spa": "Spa-Francorchamps",

    "circuit zolder": "Zolder",
    "zolder circuit": "Zolder",
    "zolder": "Zolder",

    "ecuyers": "Ecuyers",
    "écuyers": "Ecuyers",

    "croix en ternois": "Croix",
    "croix-en-ternois": "Croix",
    "croix": "Croix",

    "mettet": "Mettet",
    "assen": "Assen",
    "zandvoort": "Zandvoort",
    "meppen": "Meppen",
    "val de vienne": "Val De Vienne",
    "bilster": "Bilster Berg",
    "nürburgring": "Nürburgring",
    "nurburgring": "Nürburgring",
    "folembray": "Folembray",
    "clastres": "Clastres",
}


def clean_bad_encoding(text):
    return (
        text.replace("Â", "")
        .replace("â‚¬", "€")
        .replace("â�¬", "€")
        .replace("□", "")
        .replace("¬", "")
        .replace("\xa0", " ")
        .strip()
    )


def clean_circuit_name(name):
    name = clean_bad_encoding(name).lower().strip()
    name = name.replace("track", "").strip()

    for alias, clean_name in CIRCUIT_ALIASES.items():
        if alias in name:
            return clean_name

    return name.title()


def parse_date(date_text):
    try:
        return datetime.strptime(date_text, "%d/%m/%Y").date()
    except Exception:
        return date.max


def get_month_number(date_text):
    try:
        return datetime.strptime(date_text, "%d/%m/%Y").strftime("%m")
    except Exception:
        return ""


def format_date(date_text):
    try:
        d = datetime.strptime(date_text, "%d/%m/%Y").date()
        return f"{d.day} {DUTCH_MONTHS[d.month]} {d.year}"
    except Exception:
        return date_text


def find_text_date(text):
    lower = clean_bad_encoding(text.lower()).replace(".", "")

    pattern = r"\b(\d{1,2})(?:\s*(?:-|&)\s*\d{1,2})?\s+(jan|feb|mrt|mar|apr|mei|may|jun|jul|aug|sep|okt|oct|nov|dec|januari|februari|maart|april|juni|juli|augustus|september|oktober|november|december)\s*(2026)?\b"

    matches = re.findall(pattern, lower)

    if not matches:
        return None

    day, month_name, year = matches[-1]
    month = MONTHS.get(month_name)

    if not month:
        return None

    return f"{day.zfill(2)}/{month}/2026"


def get_intertrack_events():
    events = []
    seen = set()
    source_url = "https://www.inter-track.be"

    try:
        response = requests.get(source_url, headers=HEADERS, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        text = soup.get_text("\n")

        for line in text.splitlines():
            clean = clean_bad_encoding(line.strip())
            date_match = re.search(r"\d{2}/\d{2}/\d{4}", clean)

            if not date_match:
                continue

            date_text = date_match.group()
            parts = clean.split("-")
            circuit = clean_circuit_name(parts[-1]) if len(parts) >= 2 else "Onbekend"

            if circuit == "Onbekend":
                continue

            key = f"{date_text}-{circuit}-Intertrack"
            if key in seen:
                continue

            seen.add(key)

            events.append({
                "date": date_text,
                "date_obj": parse_date(date_text),
                "circuit": circuit,
                "organisatie": "Intertrack",
                "price": "Zie organisatie",
                "url": source_url,
                "raw": clean,
            })

    except Exception as e:
        print("Intertrack fout:", e)

    return events


def detect_trackdays_circuit(block_text):
    lines = [
        clean_bad_encoding(line.strip())
        for line in block_text.split("\n")
        if clean_bad_encoding(line.strip())
    ]

    known_circuits = list(CIRCUIT_ALIASES.keys())

    skip_words = [
        "boeken", "promotie", "vrijdag", "zaterdag", "zondag",
        "maandag", "dinsdag", "woensdag", "donderdag",
        "hemelvaart weekend", "nationale feestdag"
    ]

    for line in reversed(lines):
        lower = line.lower()
        if any(c in lower for c in known_circuits):
            return clean_circuit_name(line)

    for line in reversed(lines):
        lower = line.lower()

        if "€" in line:
            continue
        if "euro" in lower:
            continue
        if lower in skip_words:
            continue
        if re.search(r"\d", line):
            continue
        if len(line) < 3:
            continue
        if line in ["-", "–", "_"]:
            continue

        return clean_circuit_name(line)

    return None


def get_trackdays_events():
    url = "https://www.trackdays.be/nl"
    events = []
    seen = set()

    try:
        response = requests.get(url, headers=HEADERS, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")

        all_text_lines = [
            clean_bad_encoding(line.strip())
            for line in soup.get_text("\n").splitlines()
            if line.strip()
        ]

        booking_positions = [
            i for i, line in enumerate(all_text_lines)
            if line.lower() == "boeken"
        ]

        booking_links = [
            a for a in soup.find_all("a")
            if a.get("href") and "/booking/" in a.get("href")
        ]

        for index, a in enumerate(booking_links):
            if index >= len(booking_positions):
                continue

            booking_url = urljoin(url, a.get("href"))
            pos = booking_positions[index]
            nearby_lines = all_text_lines[max(0, pos - 12):pos + 1]
            nearby = "\n".join(nearby_lines)

            date_text = find_text_date(nearby)
            circuit = detect_trackdays_circuit(nearby)

            if not date_text or not circuit:
                continue

            key = f"{date_text}-{circuit}-Trackdays.be-{booking_url}"
            if key in seen:
                continue

            seen.add(key)

            events.append({
                "date": date_text,
                "date_obj": parse_date(date_text),
                "circuit": circuit,
                "organisatie": "Trackdays.be",
                "price": "Zie organisatie",
                "url": booking_url,
                "raw": " ".join(nearby_lines),
            })

    except Exception as e:
        print("Trackdays.be fout:", e)

    return events


def get_circuitdagen_events():
    url = "https://circuitdagen.be"
    events = []
    seen = set()

    skip_texts = [
        "info", "this is your heading text", "heading", "boeken",
        "beschikbaar", "plekken", "vrij rijden", "karting",
        "video laden", "groepen", "sessies", "instructie", "vanaf",
    ]

    try:
        response = requests.get(url, headers=HEADERS, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")

        lines = [
            clean_bad_encoding(line.strip()).replace("###", "").strip()
            for line in soup.get_text("\n").splitlines()
            if line.strip()
        ]

        info_links = [
            a for a in soup.find_all("a")
            if "info" in a.get_text(" ", strip=True).lower()
            and "boeken" in a.get_text(" ", strip=True).lower()
        ]

        info_counter = 0

        for i, line in enumerate(lines):
            if "info & boeken" not in line.lower():
                continue

            block = lines[max(0, i - 14):i + 1]
            block_text = " ".join(block)
            date_text = find_text_date(block_text)

            if not date_text:
                continue

            circuit = None

            for item in reversed(block):
                clean_item = clean_bad_encoding(item).strip()
                lower = clean_item.lower()

                if not clean_item:
                    continue
                if "€" in clean_item:
                    continue
                if re.search(r"\d", clean_item):
                    continue
                if len(clean_item) < 3:
                    continue
                if any(skip in lower for skip in skip_texts):
                    continue

                circuit = clean_circuit_name(clean_item)
                break

            if not circuit:
                continue

            event_url = url
            if info_counter < len(info_links):
                href = info_links[info_counter].get("href")
                if href:
                    event_url = urljoin(url, href)

            info_counter += 1

            key = f"{date_text}-{circuit}-Circuitdagen.be-{event_url}"
            if key in seen:
                continue

            seen.add(key)

            events.append({
                "date": date_text,
                "date_obj": parse_date(date_text),
                "circuit": circuit,
                "organisatie": "Circuitdagen.be",
                "price": "Zie organisatie",
                "url": event_url,
                "raw": block_text,
            })


    except Exception as e:
        print("Circuitdagen.be fout:", e)

    return events
    
def get_trackzone_events():
    url = "https://trackzone.nl/"
    events = []
    seen = set()

    try:
        response = requests.get(url, headers=HEADERS, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")

        lines = [
            clean_bad_encoding(line.strip())
            for line in soup.get_text("\n").splitlines()
            if line.strip()
        ]

        for i, line in enumerate(lines):
            date_text = find_text_date(line)

            if not date_text:
                continue

            block_lines = lines[i:i + 8]
            block_text = " ".join(block_lines)

            circuit = None

            for b in block_lines:
                lower = b.lower()

                for alias in CIRCUIT_ALIASES:
                    if alias in lower:
                        circuit = clean_circuit_name(alias)
                        break

                if circuit:
                    break

            if not circuit:
                continue

            key = f"{date_text}-{circuit}-Trackzone.nl"

            if key in seen:
                continue

            seen.add(key)

            events.append({
                "date": date_text,
                "date_obj": parse_date(date_text),
                "circuit": circuit,
                "organisatie": "Trackzone.nl",
                "price": "Zie organisatie",
                "url": url,
                "raw": block_text,
            })

    except Exception as e:
        print("Trackzone.nl fout:", e)

    return events


def get_trackdays4all_events():
    url = "https://www.trackdays4all.nl/circuittrainingen/"
    events = []

    try:
        session = requests.Session()

        response = session.get(
            url,
            headers={
                **HEADERS,
                "Referer": "https://www.google.com/",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1",
            },
            timeout=20,
            allow_redirects=True,
        )

        if response.status_code == 403:
            print("Trackdays4all geblokkeerd door anti-bot bescherming")
            return []

        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")

        lines = [
            clean_bad_encoding(line.strip())
            for line in soup.get_text("\n").splitlines()
            if line.strip()
        ]

        seen = set()

        for i, line in enumerate(lines):
            date_text = find_text_date(line)

            if not date_text:
                continue

            block = lines[max(0, i - 5):i + 8]
            block_text = " ".join(block)

            circuit = None

            for b in block:
                lower = b.lower()

                for alias in CIRCUIT_ALIASES:
                    if alias in lower:
                        circuit = clean_circuit_name(alias)
                        break

                if circuit:
                    break

            if not circuit:
                continue

            key = f"{date_text}-{circuit}-Trackdays4all"

            if key in seen:
                continue

            seen.add(key)

            events.append({
                "date": date_text,
                "date_obj": parse_date(date_text),
                "circuit": circuit,
                "organisatie": "Trackdays4all",
                "price": "Zie organisatie",
                "url": url,
                "raw": block_text,
            })

    except Exception as e:
        print("Trackdays4all fout:", e)

    return events


def scrape_events():
    events = []

    events += get_intertrack_events()
    events += get_trackdays_events()
    events += get_circuitdagen_events()
    events += get_trackzone_events()
    events += get_trackdays4all_events()

    unique = []
    seen = set()

    for event in events:
        key = f"{event['date']}-{event['circuit']}-{event['organisatie']}-{event['url']}"

        if key in seen:
            continue

        seen.add(key)
        unique.append(event)

    unique.sort(key=lambda e: e["date_obj"])

    return unique


def get_events():
    now = time.time()

    if _cache["events"] and now - _cache["time"] < CACHE_SECONDS:
        return _cache["events"]

    events = scrape_events()

    _cache["events"] = events
    _cache["time"] = now

    return events


def option_html(value, label, selected_value):
    selected = "selected" if value == selected_value else ""

    return f'<option value="{html.escape(value)}" {selected}>{html.escape(label)}</option>'


def event_to_ics(event):
    start = event["date_obj"]
    end = start + timedelta(days=1)

    uid = f"{event['date']}-{event['circuit']}-{event['organisatie']}@trackday-finder"

    return f"""BEGIN:VEVENT
UID:{uid}
DTSTAMP:{datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")}
DTSTART;VALUE=DATE:{start.strftime("%Y%m%d")}
DTEND;VALUE=DATE:{end.strftime("%Y%m%d")}
SUMMARY:Trackday - {event["circuit"]} ({event["organisatie"]})
DESCRIPTION:Organisatie: {event["organisatie"]}\\nCircuit: {event["circuit"]}\\nPrijs: {event["price"]}\\nLink: {event["url"]}
URL:{event["url"]}
END:VEVENT
"""


def make_ics(events):
    body = "BEGIN:VCALENDAR\nVERSION:2.0\nPRODID:-//Trackday Finder//NL\n"

    for event in events:
        if event["date_obj"] != date.max:
            body += event_to_ics(event)

    body += "END:VCALENDAR\n"

    return body


def build_calendar(events, cal_year, cal_month, selected_day):

    event_days = {}

    for event in events:
        d = event["date_obj"]

        if d.year == cal_year and d.month == cal_month:
            event_days.setdefault(d.day, []).append(event)

    prev_month = cal_month - 1
    prev_year = cal_year

    if prev_month == 0:
        prev_month = 12
        prev_year -= 1

    next_month = cal_month + 1
    next_year = cal_year

    if next_month == 13:
        next_month = 1
        next_year += 1

    html_cal = f"""
<div class="calendar-box">

    <div class="calendar-header">
        <a href="/?cal_year={prev_year}&cal_month={prev_month}">←</a>
        <h2>{DUTCH_MONTHS[cal_month].capitalize()} {cal_year}</h2>
        <a href="/?cal_year={next_year}&cal_month={next_month}">→</a>
    </div>

    <div class="calendar-grid calendar-days">
        <div>Ma</div>
        <div>Di</div>
        <div>Wo</div>
        <div>Do</div>
        <div>Vr</div>
        <div>Za</div>
        <div>Zo</div>
    </div>

    <div class="calendar-grid">
"""

    month_calendar = calendar.Calendar(firstweekday=0).monthdayscalendar(
        cal_year,
        cal_month
    )

    for week in month_calendar:

        for day in week:

            if day == 0:
                html_cal += '<div class="calendar-cell empty"></div>'
                continue

            events_today = event_days.get(day, [])

            day_date = date(cal_year, cal_month, day).isoformat()

            selected_class = (
                "selected-day"
                if selected_day == day_date
                else ""
            )

            if events_today:

                title = ", ".join([
                    f'{e["organisatie"]} - {e["circuit"]}'
                    for e in events_today
                ])

                html_cal += f"""
<a class="calendar-cell has-events {selected_class}"
   href="/?dag={day_date}&cal_year={cal_year}&cal_month={cal_month}"
   title="{html.escape(title)}">

    <span>{day}</span>
    <small>{len(events_today)} event(s)</small>

</a>
"""

            else:

                html_cal += f"""
<div class="calendar-cell {selected_class}">
    <span>{day}</span>
</div>
"""

    html_cal += """
    </div>
</div>
"""

    return html_cal


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/api/events")
def api_events():

    events = get_events()

    return [
        {
            "date": event["date"],
            "date_formatted": format_date(event["date"]),
            "circuit": event["circuit"],
            "organisatie": event["organisatie"],
            "price": event["price"],
            "url": event["url"],
            "raw": event["raw"],
        }
        for event in events
    ]


@app.get("/ics")
def ics_export():

    events = [
        e for e in get_events()
        if e["date_obj"] >= date.today()
    ]

    ics = make_ics(events)

    return Response(
        content=ics,
        media_type="text/calendar",
        headers={
            "Content-Disposition":
            "attachment; filename=trackdays.ics"
        },
    )


@app.get("/ics/event")
def ics_single_event(
    event_date: str = Query(...),
    circuit: str = Query(...),
    organisatie: str = Query(...),
):

    events = get_events()

    for event in events:

        if (
            event["date"] == event_date
            and event["circuit"] == circuit
            and event["organisatie"] == organisatie
        ):

            ics = make_ics([event])

    return Response(
                content=ics,
                media_type="text/calendar",
                headers={
                    "Content-Disposition":
                    "attachment; filename=trackday.ics"
                },
            )

    return Response(content="Event niet gevonden", status_code=404)
    
@app.get("/", response_class=HTMLResponse)
def home(
    q: str = Query(default=""),
    circuit: str = Query(default=""),
    organisatie: str = Query(default=""),
    maand: str = Query(default=""),
    toekomst: str = Query(default="ja"),
    sort: str = Query(default="date"),
    dag: str = Query(default=""),
    cal_year: int = Query(default=date.today().year),
    cal_month: int = Query(default=date.today().month),
    quick: str = Query(default=""),
):

    all_events = get_events()

    circuits = sorted(set(event["circuit"] for event in all_events))
    organisaties = sorted(set(event["organisatie"] for event in all_events))

    events = list(all_events)

    today = date.today()

    if toekomst == "ja":
        events = [
            e for e in events
            if e["date_obj"] >= today
        ]

    # QUICK FILTERS

    if quick == "today":

        events = [
            e for e in events
            if e["date_obj"] == today
        ]

    elif quick == "week":

        start = today
        end = today + timedelta(days=7)

        events = [
            e for e in events
            if start <= e["date_obj"] <= end
        ]

    elif quick == "month":

        events = [
            e for e in events
            if (
                e["date_obj"].month == today.month
                and e["date_obj"].year == today.year
            )
        ]

    elif quick == "nextmonth":

        next_month = today.month + 1
        next_year = today.year

        if next_month == 13:
            next_month = 1
            next_year += 1

        events = [
            e for e in events
            if (
                e["date_obj"].month == next_month
                and e["date_obj"].year == next_year
            )
        ]

    # DAG FILTER

    if dag:

        try:
            selected_date = datetime.strptime(
                dag,
                "%Y-%m-%d"
            ).date()

            events = [
                e for e in events
                if e["date_obj"] == selected_date
            ]

        except Exception:
            pass

    # SEARCH

    if q.strip():

        search = q.strip().lower()

        events = [
            e for e in events
            if (
                search in e["circuit"].lower()
                or search in e["organisatie"].lower()
                or search in e["raw"].lower()
            )
        ]

    # FILTERS

    if circuit:
        events = [
            e for e in events
            if e["circuit"] == circuit
        ]

    if organisatie:
        events = [
            e for e in events
            if e["organisatie"] == organisatie
        ]

    if maand:
        events = [
            e for e in events
            if get_month_number(e["date"]) == maand
        ]

    # SORTING

    if sort == "circuit":
        events.sort(key=lambda e: e["circuit"])

    elif sort == "organisatie":
        events.sort(key=lambda e: e["organisatie"])

    else:
        events.sort(key=lambda e: e["date_obj"])

    # OPTIONS

    circuit_options = '<option value="">Alle circuits</option>'

    for c in circuits:
        circuit_options += option_html(c, c, circuit)

    organisatie_options = '<option value="">Alle organisaties</option>'

    for org in organisaties:
        organisatie_options += option_html(org, org, organisatie)

    months_display = [
        ("", "Alle maanden"),
        ("01", "Januari"),
        ("02", "Februari"),
        ("03", "Maart"),
        ("04", "April"),
        ("05", "Mei"),
        ("06", "Juni"),
        ("07", "Juli"),
        ("08", "Augustus"),
        ("09", "September"),
        ("10", "Oktober"),
        ("11", "November"),
        ("12", "December"),
    ]

    month_options = ""

    for value, label in months_display:
        month_options += option_html(value, label, maand)

    sort_options = ""
    sort_options += option_html("date", "Sorteer op datum", sort)
    sort_options += option_html("circuit", "Sorteer op circuit", sort)
    sort_options += option_html("organisatie", "Sorteer op organisatie", sort)

    future_yes = "selected" if toekomst == "ja" else ""
    future_no = "selected" if toekomst == "nee" else ""

    safe_q = html.escape(q)

    calendar_html = build_calendar(
        all_events,
        cal_year,
        cal_month,
        dag
    )

    selected_day_text = ""

    if dag:
        selected_day_text = f'''
<p class="selected-info">
    Geselecteerde dag: {html.escape(dag)}
    —
    <a href="/">toon alles</a>
</p>
'''

    html_page = f"""
<!DOCTYPE html>
<html lang="nl">

<head>
<meta charset="UTF-8">
<title>Trackday Finder</title>

<style>

body {{
    margin: 0;
    font-family: Arial, sans-serif;
    background: #111827;
}}

.header {{
    padding: 40px 20px;
    text-align: center;
    color: white;
}}

.container {{
    max-width: 1150px;
    margin: auto;
    padding: 20px;
}}

.searchbox,
.calendar-box {{
    background: white;
    padding: 20px;
    border-radius: 16px;
    margin-bottom: 20px;
}}

.searchbox {{
    position: sticky;
    top: 0;
    z-index: 100;
}}

.filters {{
    display: grid;
    grid-template-columns:
        1.5fr
        1fr
        1fr
        1fr
        1fr
        1fr
        auto;

    gap: 10px;
}}

input,
select {{
    padding: 15px;
    border-radius: 10px;
    border: 1px solid #ddd;
    font-size: 16px;
    width: 100%;
    box-sizing: border-box;
}}

button {{
    padding: 15px 25px;
    border: none;
    border-radius: 10px;
    background: #ef4444;
    color: white;
    font-size: 16px;
    font-weight: bold;
    cursor: pointer;
}}

button:hover {{
    background: #dc2626;
}}

.reset,
.ics-all {{
    display: inline-block;
    margin-top: 12px;
    color: #ef4444;
    text-decoration: none;
    font-weight: bold;
}}

.ics-all {{
    margin-left: 18px;
    color: #111827;
}}

.quick-filters {{
    margin-top: 20px;
    display: flex;
    flex-wrap: wrap;
    gap: 10px;
}}

.quick-filters a {{
    background: #111827;
    color: white;
    padding: 10px 14px;
    border-radius: 999px;
    text-decoration: none;
    font-size: 14px;
    font-weight: bold;
}}

.quick-filters a:hover {{
    background: #374151;
}}

.count {{
    color: white;
    margin-bottom: 15px;
}}

.selected-info {{
    color: white;
    font-weight: bold;
}}

.selected-info a {{
    color: #fca5a5;
}}

.card {{
    background: white;
    padding: 20px;
    border-radius: 16px;
    margin-bottom: 15px;
}}

.badge {{
    display: inline-block;
    background: #fee2e2;
    color: #991b1b;
    padding: 6px 10px;
    border-radius: 999px;
    font-size: 13px;
    font-weight: bold;
    margin-bottom: 10px;
}}

.circuit {{
    font-size: 28px;
    font-weight: bold;
    margin-bottom: 10px;
}}

.meta {{
    margin: 6px 0;
}}

.price {{
    display: inline-block;
    margin-top: 8px;
    padding: 8px 12px;
    background: #ecfdf5;
    color: #065f46;
    border-radius: 999px;
    font-weight: bold;
}}

.raw {{
    color: #666;
    font-size: 13px;
    margin-top: 10px;
    line-height: 1.4;
}}

.link-button,
.ics-button {{
    display: inline-block;
    margin-top: 14px;
    padding: 10px 14px;
    background: #111827;
    color: white;
    border-radius: 10px;
    text-decoration: none;
    font-weight: bold;
}}

.ics-button {{
    background: #065f46;
    margin-left: 8px;
}}

.link-button:hover {{
    background: #374151;
}}

.ics-button:hover {{
    background: #047857;
}}

.calendar-header {{
    display: flex;
    justify-content: space-between;
    align-items: center;
}}

.calendar-header a {{
    font-size: 28px;
    text-decoration: none;
    color: #ef4444;
    font-weight: bold;
}}

.calendar-header h2 {{
    margin: 0 0 15px 0;
}}

.calendar-grid {{
    display: grid;
    grid-template-columns: repeat(7, 1fr);
    gap: 8px;
}}

.calendar-days div {{
    font-weight: bold;
    text-align: center;
    padding: 8px;
}}

.calendar-cell {{
    min-height: 75px;
    background: #f3f4f6;
    border-radius: 12px;
    padding: 10px;
    text-decoration: none;
    color: #111827;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
}}

.calendar-cell span {{
    font-weight: bold;
}}

.calendar-cell small {{
    font-size: 12px;
}}

.calendar-cell.empty {{
    background: transparent;
}}

.calendar-cell.has-events {{
    background: #fee2e2;
    border: 2px solid #ef4444;
}}

.calendar-cell.has-events:hover {{
    background: #fecaca;
}}

.selected-day {{
    outline: 3px solid #111827;
}}

@media (max-width: 1050px) {{

    .filters {{
        grid-template-columns: 1fr;
    }}

    .searchbox {{
        position: static;
    }}

    .calendar-cell {{
        min-height: 55px;
        padding: 7px;
    }}

    .calendar-cell small {{
        font-size: 10px;
    }}
}}

</style>
</head>

<body>

<div class="header">
    <h1>Trackday Finder</h1>
    <p>
        Zoek en filter trackdays
        op circuit,
        organisatie
        en maand
    </p>
</div>

<div class="container">

    <div class="searchbox">

        <form method="get" action="/" class="filters">

            <input
                type="text"
                name="q"
                placeholder="Vrij zoeken..."
                value="{safe_q}"
            >

            <select name="circuit">
                {circuit_options}
            </select>

            <select name="organisatie">
                {organisatie_options}
            </select>

            <select name="maand">
                {month_options}
            </select>

            <select name="toekomst">
                <option value="ja" {future_yes}>
                    Alleen toekomst
                </option>

                <option value="nee" {future_no}>
                    Alles tonen
                </option>
            </select>

            <select name="sort">
                {sort_options}
            </select>

            <button type="submit">
                Zoeken
            </button>

        </form>

        <a class="reset" href="/">
            Filters wissen
        </a>

        <a class="ics-all" href="/ics">
            Download alle trackdays (.ics)
        </a>

        <div class="quick-filters">

            <a href="/?quick=today">
                Vandaag
            </a>

            <a href="/?quick=week">
                Deze week
            </a>

            <a href="/?quick=month">
                Deze maand
            </a>

            <a href="/?quick=nextmonth">
                Volgende maand
            </a>

            <a href="/">
                Alles
            </a>

        </div>

    </div>

    {calendar_html}

    {selected_day_text}

    <p class="count">
        Resultaten: {len(events)}
    </p>
"""

    if len(events) == 0:

        html_page += """
<div class="card">
    Geen resultaten gevonden.
</div>
"""

    else:

        for event in events:

            event_org = html.escape(event["organisatie"])
            event_circuit = html.escape(event["circuit"])
            event_date = html.escape(format_date(event["date"]))
            event_price = html.escape(event["price"])
            event_raw = html.escape(event["raw"])
            event_url = html.escape(event["url"])

            ics_url = (
                f"/ics/event?event_date={quote(event['date'])}"
                f"&circuit={quote(event['circuit'])}"
                f"&organisatie={quote(event['organisatie'])}"
            )

            html_page += f"""
<div class="card">

    <div class="badge">
        {event_org}
    </div>

    <div class="circuit">
        {event_circuit}
    </div>

    <div class="meta">
        <b>Datum:</b>
        {event_date}
    </div>

    <div class="meta">
        <b>Organisatie:</b>
        {event_org}
    </div>

    <div class="price">
        Prijs: {event_price}
    </div>

    <div class="raw">
        {event_raw}
    </div>

    <a
        class="link-button"
        href="{event_url}"
        target="_blank"
    >
        Bekijk / boeken bij {event_org}
    </a>

    <a
        class="ics-button"
        href="{ics_url}"
    >
        Zet in agenda
    </a>

</div>
"""

    html_page += """
</div>
</body>
</html>
"""

    return html_page
