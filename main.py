from fastapi import FastAPI, Query
from fastapi.responses import HTMLResponse
import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime

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


def sort_date(date_text):
    try:
        return datetime.strptime(date_text, "%d/%m/%Y")
    except:
        return datetime.max


def get_intertrack_events():
    events = []
    seen = set()
    source_url = "https://www.inter-track.be"

    try:
        r = requests.get(source_url, headers=HEADERS, timeout=10)
        soup = BeautifulSoup(r.text, "html.parser")
        text = soup.get_text("\n")

        for line in text.splitlines():
            clean = line.strip()

            if not clean:
                continue

            date_match = re.search(r"\d{2}/\d{2}/\d{4}", clean)

            if not date_match:
                continue

            date = date_match.group()

            parts = clean.split("-")
            if len(parts) >= 2:
                circuit = clean_circuit_name(parts[-1])
            else:
                circuit = "Onbekend"

            if circuit == "Onbekend":
                continue

            key = f"{date}-{circuit}-Intertrack"

            if key in seen:
                continue

            seen.add(key)

            events.append({
                "date": date,
                "circuit": circuit,
                "organisatie": "Intertrack",
                "url": source_url,
                "raw": clean
            })

    except Exception as e:
        print("Intertrack fout:", e)

    return events


def get_trackdays_events():
    urls = [
        "https://www.trackdays.be/nl",
        "https://www.trackdays.be/fr",
        "https://www.trackdays.be/en",
    ]

    events = []
    seen = set()

    for url in urls:
        try:
            r = requests.get(url, headers=HEADERS, timeout=10)
            soup = BeautifulSoup(r.text, "html.parser")
            lines = [line.strip() for line in soup.get_text("\n").splitlines() if line.strip()]

            for i, line in enumerate(lines):
                lower = line.lower()

                if not lower.startswith("track "):
                    continue

                circuit = clean_circuit_name(line)
                nearby = " ".join(lines[max(0, i - 8): i + 8])
                date = find_trackdays_date(nearby)

                if not date:
                    continue

                key = f"{date}-{circuit}-Trackdays.be"

                if key in seen:
                    continue

                seen.add(key)

                events.append({
                    "date": date,
                    "circuit": circuit,
                    "organisatie": "Trackdays.be",
                    "url": url,
                    "raw": nearby
                })

        except Exception as e:
            print("Trackdays.be fout:", url, e)

    return events


def get_events():
    events = []
    events += get_intertrack_events()
    events += get_trackdays_events()

    unique = []
    seen = set()

    for e in events:
        key = f"{e['date']}-{e['circuit']}-{e['organisatie']}"

        if key in seen:
            continue

        seen.add(key)
        unique.append(e)

    unique.sort(key=lambda e: sort_date(e["date"]))
    return unique


def option_html(value, selected_value):
    selected = "selected" if value == selected_value else ""
    return f'<option value="{value}" {selected}>{value}</option>'


@app.get("/", response_class=HTMLResponse)
def home(
    q: str = Query(default=""),
    circuit: str = Query(default=""),
    organisatie: str = Query(default="")
):
    all_events = get_events()

    circuits = sorted(set(e["circuit"] for e in all_events))
    organisaties = sorted(set(e["organisatie"] for e in all_events))

    events = all_events

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

    circuit_options = '<option value="">Alle circuits</option>'
    for c in circuits:
        circuit_options += option_html(c, circuit)

    organisatie_options = '<option value="">Alle organisaties</option>'
    for o in organisaties:
        organisatie_options += option_html(o, organisatie)

    html = f"""
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

            .container {{
                max-width: 1100px;
                margin: auto;
                padding: 20px;
            }}

            .searchbox {{
                background: white;
                padding: 20px;
                border-radius: 16px;
                margin-bottom: 20px;
            }}

            .filters {
    display: grid;
    grid-template-columns: 1.5fr 1fr 1fr 1fr 1fr auto;
    gap: 10px;
}

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

            .raw {{
                color: #666;
                font-size: 13px;
                margin-top: 10px;
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

            @media (max-width: 800px) {{
                .filters {{
                    grid-template-columns: 1fr;
                }}
            }}
        </style>
    </head>

    <body>
        <div class="header">
            <h1>Trackday Finder</h1>
            <p>VERSIE 2 - filters actief</p>
        </div>

        <div class="container">
            <div class="searchbox">
                <form method="get" action="/" class="filters">

    <input
        type="text"
        name="q"
        placeholder="Vrij zoeken..."
        value="{q}"
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

    <button type="submit">
        Zoeken
    </button>

</form>
                <a class="reset" href="/">Filters wissen</a>
            </div>

            <p style="color:white;">Resultaten: {len(events)}</p>
    """

    if len(events) == 0:
        html += '<div class="card">Geen resultaten gevonden.</div>'
    else:
        for e in events:
            html += f"""
            <div class="card">
                <div class="badge">{e["organisatie"]}</div>
                <div class="circuit">{e["circuit"]}</div>
                <div class="meta"><b>Datum:</b> {e["date"]}</div>
                <div class="meta"><b>Organisatie:</b> {e["organisatie"]}</div>
                <div class="raw">{e["raw"]}</div>
                <a class="link-button" href="{e["url"]}" target="_blank">
                    Bekijk / boeken bij {e["organisatie"]}
                </a>
            </div>
            """

    html += """
        </div>
    </body>
    </html>
    """

    return html
