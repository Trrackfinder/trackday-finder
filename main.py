from fastapi import FastAPI, Query
from fastapi.responses import HTMLResponse
import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime

app = FastAPI()

HEADERS = {"User-Agent": "Mozilla/5.0"}

CIRCUITS = [
    "Mettet",
    "Croix",
    "Croix-en-Ternois",
    "Spa",
    "Zandvoort",
    "Assen",
    "Zolder",
    "Ecuyers",
    "Clastres",
    "Nürburgring",
    "Magny-Cours",
    "Dijon",
    "Le Mans",
]

MONTHS = {
    "jan": "01", "feb": "02", "mrt": "03", "mar": "03",
    "apr": "04", "mei": "05", "may": "05", "jun": "06",
    "jul": "07", "aug": "08", "sep": "09", "okt": "10",
    "oct": "10", "nov": "11", "dec": "12",
}


def detect_circuit(text):
    lower = text.lower()

    for circuit in CIRCUITS:
        if circuit.lower() in lower:
            if circuit == "Croix-en-Ternois":
                return "Croix"
            return circuit

    return None


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


def get_intertrack_events():
    events = []
    seen = set()

    try:
        r = requests.get("https://www.inter-track.be", headers=HEADERS, timeout=10)
        soup = BeautifulSoup(r.text, "html.parser")
        text = soup.get_text("\n")

        for line in text.splitlines():
            clean = line.strip()

            if not clean:
                continue

            circuit = detect_circuit(clean)

            if not circuit:
                continue

            date_match = re.search(r"\d{2}/\d{2}/\d{4}", clean)

            if not date_match:
                continue

            date = date_match.group()
            key = f"{date}-{circuit}-Intertrack"

            if key in seen:
                continue

            seen.add(key)

            events.append({
                "date": date,
                "circuit": circuit,
                "organisatie": "Intertrack",
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

            lines = [
                line.strip()
                for line in soup.get_text("\n").splitlines()
                if line.strip()
            ]

            for i, line in enumerate(lines):
                circuit = detect_circuit(line)

                if not circuit:
                    continue

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
                    "raw": nearby
                })

        except Exception as e:
            print("Trackdays.be fout:", url, e)

    return events


def sort_date(date_text):
    try:
        return datetime.strptime(date_text, "%d/%m/%Y")
    except:
        return datetime.max


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


@app.get("/", response_class=HTMLResponse)
def home(q: str = Query(default="")):
    all_events = get_events()
    search = q.strip().lower()

    if search:
        events = [
            e for e in all_events
            if search in e["circuit"].lower()
            or search in e["organisatie"].lower()
            or search in e["raw"].lower()
        ]
    else:
        events = all_events

    html = f"""
    <html>
    <head>
        <title>Trackday Finder</title>
        <style>
            body {{
                margin: 0;
                font-family: Arial;
                background: #111827;
            }}

            .header {{
                padding: 40px 20px;
                text-align: center;
                color: white;
            }}

            .container {{
                max-width: 1000px;
                margin: auto;
                padding: 20px;
            }}

            .searchbox {{
                background: white;
                padding: 20px;
                border-radius: 16px;
                margin-bottom: 20px;
            }}

            input {{
                width: 70%;
                padding: 15px;
                border-radius: 10px;
                border: 1px solid #ddd;
                font-size: 16px;
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

            .raw {{
                color: #666;
                font-size: 13px;
                margin-top: 10px;
            }}
        </style>
    </head>

    <body>
        <div class="header">
            <h1>Trackday Finder</h1>
            <p>Zoek alle trackdays op circuit of organisatie</p>
        </div>

        <div class="container">
            <div class="searchbox">
                <form method="get" action="/">
                    <input
                        type="text"
                        name="q"
                        placeholder="Zoek circuit of organisatie..."
                        value="{q}"
                    >
                    <button type="submit">Zoeken</button>
                </form>
            </div>

            <p style="color:white;">Resultaten: {len(events)}</p>
    """

    if len(events) == 0:
        html += """
        <div class="card">
            Geen resultaten gevonden.
        </div>
        """
    else:
        for e in events:
            html += f"""
            <div class="card">
                <div class="badge">{e["organisatie"]}</div>
                <div class="circuit">{e["circuit"]}</div>
                <div class="meta"><b>Datum:</b> {e["date"]}</div>
                <div class="meta"><b>Organisatie:</b> {e["organisatie"]}</div>
                <div class="raw">{e["raw"]}</div>
            </div>
            """

    html += """
        </div>
    </body>
    </html>
    """

    return html
