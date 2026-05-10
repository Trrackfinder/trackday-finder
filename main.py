from fastapi import FastAPI
from fastapi.responses import HTMLResponse
import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime

app = FastAPI()

HEADERS = {
    "User-Agent": "Mozilla/5.0"
}


def parse_date(text):
    patterns = [
        r"\d{2}/\d{2}/\d{4}",
        r"\d{1,2}/\d{1,2}/\d{4}",
        r"\d{1,2}-\d{1,2}-\d{4}",
        r"\d{1,2}\s+(januari|februari|maart|april|mei|juni|juli|augustus|september|oktober|november|december)\s+\d{4}",
        r"\d{1,2}\s+(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\s+\d{4}",
    ]

    lower = text.lower()

    for pattern in patterns:
        match = re.search(pattern, lower)
        if match:
            return match.group().replace("-", "/")

    return "Onbekend"


def extract_events_from_text(text, organisatie):
    events = []
    seen = set()
    lines = [line.strip() for line in text.splitlines() if line.strip()]

    for i, line in enumerate(lines):
        lower = line.lower()

        if "mettet" not in lower and "croix" not in lower:
            continue

        nearby_lines = lines[max(0, i - 10): i + 11]
        nearby_text = " ".join(nearby_lines)

        date = parse_date(nearby_text)
        circuit = "Mettet" if "mettet" in lower else "Croix"

        key = f"{date}-{circuit}-{organisatie}-{nearby_text[:80]}"

        if key in seen:
            continue

        seen.add(key)

        events.append({
            "date": date,
            "circuit": circuit,
            "organisatie": organisatie,
            "raw": nearby_text
        })

    return events


def get_intertrack_events():
    try:
        r = requests.get("https://www.inter-track.be", headers=HEADERS, timeout=10)
        soup = BeautifulSoup(r.text, "html.parser")
        return extract_events_from_text(soup.get_text("\n"), "Intertrack")
    except Exception as e:
        print("Intertrack fout:", e)
        return []


def get_trackdays_events():
    urls = [
        "https://www.trackdays.be/nl",
        "https://www.trackdays.be/fr",
        "https://www.trackdays.be/en",
    ]

    events = []

    for url in urls:
        try:
            r = requests.get(url, headers=HEADERS, timeout=10)
            soup = BeautifulSoup(r.text, "html.parser")
            events += extract_events_from_text(soup.get_text("\n"), "Trackdays.be")
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
        key = f"{e['date']}-{e['circuit']}-{e['organisatie']}-{e['raw'][:60]}"
        if key in seen:
            continue
        seen.add(key)
        unique.append(e)

    unique.sort(key=lambda e: sort_date(e["date"]))
    return unique


@app.get("/", response_class=HTMLResponse)
def home():
    events = get_events()

    html = """
    <html>
    <head>
        <title>Trackday Finder</title>
        <style>
            body {
                font-family: Arial;
                max-width: 900px;
                margin: auto;
                padding: 20px;
                background: #f5f5f5;
            }

            .card {
                background: white;
                padding: 15px;
                border-radius: 10px;
                margin-bottom: 10px;
                box-shadow: 0 2px 6px rgba(0,0,0,0.08);
            }

            .circuit {
                font-size: 22px;
                font-weight: bold;
            }

            small {
                color: #666;
            }
        </style>
    </head>
    <body>
        <h1>Trackday Finder</h1>
        <p>Mettet & Croix trackdays</p>
    """

    if len(events) == 0:
        html += "<p>Geen events gevonden.</p>"

    for e in events:
        html += f"""
        <div class="card">
            <div class="circuit">{e["circuit"]}</div>
            <p><b>Datum:</b> {e["date"]}</p>
            <p><b>Organisatie:</b> {e["organisatie"]}</p>
            <p><small>{e["raw"]}</small></p>
        </div>
        """

    html += """
    </body>
    </html>
    """

    return html


@app.get("/trackdays-debug", response_class=HTMLResponse)
def trackdays_debug():
    urls = [
        "https://www.trackdays.be/nl",
        "https://www.trackdays.be/fr",
        "https://www.trackdays.be/en",
    ]

    html = "<h1>Trackdays.be debug</h1>"

    for url in urls:
        try:
            r = requests.get(url, headers=HEADERS, timeout=10)
            soup = BeautifulSoup(r.text, "html.parser")
            text = soup.get_text("\n")
            lines = [line.strip() for line in text.splitlines() if line.strip()]

            html += f"<h2>{url}</h2><p>Status: {r.status_code}</p>"

            for i, line in enumerate(lines):
                lower = line.lower()

                if "mettet" in lower or "croix" in lower:
                    snippet = "<br>".join(lines[max(0, i - 10): i + 11])
                    html += f"""
                    <div style="border:1px solid #ccc; padding:10px; margin:10px;">
                        {snippet}
                    </div>
                    """

        except Exception as e:
            html += f"<p>Fout: {e}</p>"

    return html
