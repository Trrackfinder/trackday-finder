from fastapi import FastAPI, Query
from fastapi.responses import HTMLResponse
import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime, date
from urllib.parse import urljoin

app = FastAPI()

HEADERS = {"User-Agent": "Mozilla/5.0"}

MONTHS = {
    "jan": "01", "feb": "02", "mrt": "03", "mar": "03",
    "apr": "04", "mei": "05", "may": "05", "jun": "06",
    "jul": "07", "aug": "08", "sep": "09", "okt": "10",
    "oct": "10", "nov": "11", "dec": "12",
}


def clean_circuit_name(name):
    name = name.replace("track", "").strip()
    name = name.replace("croix en ternois", "Croix")
    name = name.replace("croix-en-ternois", "Croix")
    return name.title()


def find_trackdays_date(text):
    lower = text.lower().replace(".", "")
    pattern = r"\b(\d{1,2})(?:\s*-\s*\d{1,2})?\s+(jan|feb|mrt|mar|apr|mei|may|jun|jul|aug|sep|okt|oct|nov|dec)\b"
    matches = re.findall(pattern, lower)

    if not matches:
        return None

    day, month_name = matches[-1]
    month = MONTHS.get(month_name)

    if not month:
        return None

    return f"{day.zfill(2)}/{month}/2026"


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


def get_intertrack_events():
    events = []
    seen = set()
    source_url = "https://www.inter-track.be"

    try:
        response = requests.get(source_url, headers=HEADERS, timeout=10)
        soup = BeautifulSoup(response.text, "html.parser")
        text = soup.get_text("\n")

        for line in text.splitlines():
            clean = line.strip()

            if not clean:
                continue

            date_match = re.search(r"\d{2}/\d{2}/\d{4}", clean)

            if not date_match:
                continue

            date_text = date_match.group()

            parts = clean.split("-")
            if len(parts) >= 2:
                circuit = clean_circuit_name(parts[-1])
            else:
                circuit = "Onbekend"

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
    lines = [line.strip() for line in block_text.split("\n") if line.strip()]

    skip_words = [
        "boeken", "promotie", "vrijdag", "zaterdag", "zondag", "maandag",
        "dinsdag", "woensdag", "donderdag", "hemelvaart weekend",
        "nationale feestdag"
    ]

    for line in reversed(lines):
        lower = line.lower()

        if lower.startswith("track "):
            return clean_circuit_name(line)

        if "€" in line or "â¬" in line:
            continue

        if re.search(r"\d", line):
            continue

        if lower in skip_words:
            continue

        if len(line) > 2:
            return clean_circuit_name(line)

    return None


def get_trackdays_events():
    url = "https://www.trackdays.be/nl"
    events = []
    seen = set()

    try:
        response = requests.get(url, headers=HEADERS, timeout=10)
        soup = BeautifulSoup(response.text, "html.parser")

        all_text_lines = [
            line.strip()
            for line in soup.get_text("\n").splitlines()
            if line.strip()
        ]

        for a in soup.find_all("a"):
            href = a.get("href")
            link_text = a.get_text(" ", strip=True).lower()

            if not href or "/booking/" not in href:
                continue

            booking_url = urljoin(url, href)

            flat_text = soup.get_text("\n")
            booking_text = a.get_text(" ", strip=True)

            lines = all_text_lines

            booking_positions = [
                i for i, line in enumerate(lines)
                if line.lower() == "boeken"
            ]

            booking_number = 0
            for previous_a in soup.find_all("a"):
                previous_href = previous_a.get("href")
                if previous_href and "/booking/" in previous_href:
                    if previous_a == a:
                        break
                    booking_number += 1

            if booking_number >= len(booking_positions):
                continue

            pos = booking_positions[booking_number]
            nearby_lines = lines[max(0, pos - 12):pos + 1]
            nearby = "\n".join(nearby_lines)

            date_text = find_trackdays_date(nearby)
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


def get_events():
    events = []
    events += get_intertrack_events()
    events += get_trackdays_events()

    unique = []
    seen = set()

    for event in events:
        key = f"{event['date']}-{event['circuit']}-{event['organisatie']}"

        if key in seen:
            continue

        seen.add(key)
        unique.append(event)

    unique.sort(key=lambda event: event["date_obj"])
    return unique


def option_html(value, label, selected_value):
    selected = "selected" if value == selected_value else ""
    return f'<option value="{value}" {selected}>{label}</option>'


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
        events = [event for event in events if event["date_obj"] >= today]

    if q.strip():
        search = q.strip().lower()
        events = [
            event for event in events
            if search in event["circuit"].lower()
            or search in event["organisatie"].lower()
            or search in event["raw"].lower()
        ]

    if circuit:
        events = [event for event in events if event["circuit"] == circuit]

    if organisatie:
        events = [event for event in events if event["organisatie"] == organisatie]

    if maand:
        events = [event for event in events if get_month_number(event["date"]) == maand]

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

    html = f"""
<!DOCTYPE html>
<html>
<head>
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

        .header h1 {{
            margin: 0;
            font-size: 42px;
        }}

        .header p {{
            color: #d1d5db;
            font-size: 18px;
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
            box-shadow: 0 8px 24px rgba(0,0,0,0.20);
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
            box-shadow: 0 8px 24px rgba(0,0,0,0.20);
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

            .header h1 {{
                font-size: 34px;
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
                <input type="text" name="q" placeholder="Vrij zoeken..." value="{q}">
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
        html += """
        <div class="card">
            Geen resultaten gevonden.
        </div>
        """
    else:
        for event in events:
            html += f"""
        <div class="card">
            <div class="badge">{event["organisatie"]}</div>
            <div class="circuit">{event["circuit"]}</div>
            <div class="meta"><b>Datum:</b> {event["date"]}</div>
            <div class="meta"><b>Organisatie:</b> {event["organisatie"]}</div>
            <div class="price">Prijs: {event["price"]}</div>
            <div class="raw">{event["raw"]}</div>
            <a class="link-button" href="{event["url"]}" target="_blank">
                Bekijk / boeken bij {event["organisatie"]}
            </a>
        </div>
"""

    html += """
    </div>
</body>
</html>
"""

    return html
