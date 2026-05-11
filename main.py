from fastapi import FastAPI, Query
from fastapi.responses import HTMLResponse
import requests
from bs4 import BeautifulSoup
import re
import time
import html
from datetime import datetime, date
from urllib.parse import urljoin

app = FastAPI()

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "nl-NL,nl;q=0.9,en-US;q=0.8,en;q=0.7",
    "Referer": "https://www.google.com/",
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

    replacements = {
        "track": "",
        "croix en ternois": "Croix",
        "croix-en-ternois": "Croix",
        "circuit de spa-francorchamps": "Spa-Francorchamps",
        "spa francorchamps": "Spa-Francorchamps",
        "spa-francorchamps": "Spa-Francorchamps",
        "zolder circuit": "Zolder",
        "circuit zolder": "Zolder",
        "val de vienne": "Val De Vienne",
        "ecuyers": "Ecuyers",
        "écuyers": "Ecuyers",
        "meppen": "Meppen",
        "assen": "Assen",
        "mettet": "Mettet",
    }

    for old, new in replacements.items():
        name = name.replace(old, new)

    return name.strip().title()


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
        maanden = [
            "", "januari", "februari", "maart", "april", "mei", "juni",
            "juli", "augustus", "september", "oktober", "november", "december"
        ]
        return f"{d.day} {maanden[d.month]} {d.year}"
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

            if not clean:
                continue

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
                "raw": clean
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

    known_circuits = [
        "zolder", "spa", "francorchamps", "mettet", "croix", "ternois",
        "clastres", "folembray", "ecuyers", "écuyers", "meppen",
        "bilster", "nürburgring", "nurburgring", "assen", "zandvoort",
    ]

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
                "raw": " ".join(nearby_lines)
            })

    except Exception as e:
        print("Trackdays.be fout:", e)

    return events


def get_circuitdagen_events():
    url = "https://circuitdagen.be"
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
            if "info & boeken" not in line.lower():
                continue

            block = lines[max(0, i - 10):i + 1]
            block_text = " ".join(block)
            date_text = find_text_date(block_text)

            if not date_text:
                continue

            circuit = None

            for item in reversed(block):
                lower = item.lower()

                if "€" in item:
                    continue

                if re.search(r"\d", item):
                    continue

                if len(item) < 3:
                    continue

                if "info" in lower:
                    continue

                circuit = clean_circuit_name(item)
                break

            if not circuit:
                continue

            key = f"{date_text}-{circuit}-Circuitdagen.be"

            if key in seen:
                continue

            seen.add(key)

            events.append({
                "date": date_text,
                "date_obj": parse_date(date_text),
                "circuit": circuit,
                "organisatie": "Circuitdagen.be",
                "price": "Zie organisatie",
                "url": url,
                "raw": block_text
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

                if "meppen" in lower:
                    circuit = "Meppen"
                elif "ecuyers" in lower or "écuyers" in lower:
                    circuit = "Ecuyers"
                elif "zolder" in lower:
                    circuit = "Zolder"
                elif "spa" in lower:
                    circuit = "Spa-Francorchamps"

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
                "raw": block_text
            })

    except Exception as e:
        print("Trackzone.nl fout:", e)

    return events


def get_trackdays4all_events():
    url = "https://www.trackdays4all.nl/circuittrainingen/"
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

        known_circuits = [
            "assen", "ecuyers", "écuyers", "val de vienne", "zolder",
            "spa", "mettet", "croix", "meppen", "zandvoort"
        ]

        for i, line in enumerate(lines):
            date_text = find_text_date(line)

            if not date_text:
                continue

            block = lines[max(0, i - 5):i + 8]
            block_text = " ".join(block)

            circuit = None

            for b in block:
                b_lower = b.lower()

                for known in known_circuits:
                    if known in b_lower:
                        circuit = clean_circuit_name(known)
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
                "raw": block_text
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


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/", response_class=HTMLResponse)
def home(
    q: str = Query(default=""),
    circuit: str = Query(default=""),
    organisatie: str = Query(default=""),
    maand: str = Query(default=""),
    toekomst: str = Query(default="ja")
):
    all_events = get_events()

    circuits = sorted(set(event["circuit"] for event in all_events))
    organisaties = sorted(set(event["organisatie"] for event in all_events))

    events = all_events

    if toekomst == "ja":
        today = date.today()
        events = [e for e in events if e["date_obj"] >= today]

    if q.strip():
        search = q.strip().lower()
        events = [
            e for e in events
            if search in e["circuit"].lower()
            or search in e["organisatie"].lower()
            or search in e["raw"].lower()
        ]

    if circuit:
        events = [e for e in events if e["circuit"] == circuit]

    if organisatie:
        events = [e for e in events if e["organisatie"] == organisatie]

    if maand:
        events = [e for e in events if get_month_number(e["date"]) == maand]

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

    future_yes = "selected" if toekomst == "ja" else ""
    future_no = "selected" if toekomst == "nee" else ""

    safe_q = html.escape(q)

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

.searchbox {{
    background: white;
    padding: 20px;
    border-radius: 16px;
    margin-bottom: 20px;
}}

.filters {{
    display: grid;
    grid-template-columns: 1.5fr 1fr 1fr 1fr 1fr auto;
    gap: 10px;
}}

input, select {{
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

.reset {{
    display: inline-block;
    margin-top: 12px;
    color: #ef4444;
    text-decoration: none;
    font-weight: bold;
}}

.count {{
    color: white;
    margin-bottom: 15px;
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

.link-button {{
    display: inline-block;
    margin-top: 14px;
    padding: 10px 14px;
    background: #111827;
    color: white;
    border-radius: 10px;
    text-decoration: none;
    font-weight: bold;
}}

.link-button:hover {{
    background: #374151;
}}

@media (max-width: 950px) {{
    .filters {{
        grid-template-columns: 1fr;
    }}
}}
</style>
</head>
<body>

<div class="header">
    <h1>Trackday Finder</h1>
    <p>Zoek en filter trackdays op circuit, organisatie en maand</p>
</div>

<div class="container">
    <div class="searchbox">
        <form method="get" action="/" class="filters">
            <input type="text" name="q" placeholder="Vrij zoeken..." value="{safe_q}">
            <select name="circuit">{circuit_options}</select>
            <select name="organisatie">{organisatie_options}</select>
            <select name="maand">{month_options}</select>
            <select name="toekomst">
                <option value="ja" {future_yes}>Alleen toekomst</option>
                <option value="nee" {future_no}>Alles tonen</option>
            </select>
            <button type="submit">Zoeken</button>
        </form>

        <a class="reset" href="/">Filters wissen</a>
    </div>

    <p class="count">Resultaten: {len(events)}</p>
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

            html_page += f"""
    <div class="card">
        <div class="badge">{event_org}</div>
        <div class="circuit">{event_circuit}</div>
        <div class="meta"><b>Datum:</b> {event_date}</div>
        <div class="meta"><b>Organisatie:</b> {event_org}</div>
        <div class="price">Prijs: {event_price}</div>
        <div class="raw">{event_raw}</div>
        <a class="link-button" href="{event_url}" target="_blank">
            Bekijk / boeken bij {event_org}
        </a>
    </div>
"""

    html_page += """
</div>
</body>
</html>
"""

    return html_page
