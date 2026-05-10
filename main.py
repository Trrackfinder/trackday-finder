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
    match = re.search(r"\d{2}/\d{2}/\d{4}", text)
    if match:
        return match.group()

    match = re.search(r"\d{1,2}-\d{1,2}-\d{4}", text)
    if match:
        return match.group().replace("-", "/")

    return None


def extract_events_from_lines(text, organisatie):
    events = []
    seen = set()
    lines = text.splitlines()

    for i, line in enumerate(lines):
        clean = line.strip()
        lower = clean.lower()

        if "mettet" not in lower and "croix" not in lower:
            continue

        nearby_text = " ".join(lines[max(0, i - 3): i + 4])
        date = parse_date(nearby_text)

        if not date:
            continue

        circuit = "Mettet" if "mettet" in lower else "Croix"
        key = f"{date}-{circuit}-{organisatie}"

        if key in seen:
            continue

        seen.add(key)

        events.append({
            "date": date,
            "circuit": circuit,
            "organisatie": organisatie,
            "raw": nearby_text.strip()
        })

    return events


def get_intertrack_events():
    url = "https://www.inter-track.be"

    try:
        r = requests.get(url, headers=HEADERS, timeout=10)
        soup = BeautifulSoup(r.text, "html.parser")
        return extract_events_from_lines(soup.get_text("\n"), "Intertrack")

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
            text = soup.get_text("\n")
            events += extract_events_from_lines(text, "Trackdays.be")

        except Exception as e:
            print("Trackdays.be fout:", url, e)

    return events


def normalize_date_for_sort(date_text):
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

    unique.sort(key=lambda e: normalize_date_for_sort(e["date"]))

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

            h1 {
                margin-bottom: 5px;
            }

            .subtitle {
                color: #555;
                margin-bottom: 25px;
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

            .meta {
                margin-top: 8px;
                color: #333;
            }

            small {
                color: #777;
            }
        </style>
    </head>
    <body>
        <h1>Trackday Finder</h1>
        <p class="subtitle">Mettet & Croix trackdays</p>
    """

    if len(events) == 0:
        html += "<p>Geen events gevonden.</p>"

    for e in events:
        html += f"""
        <div class="card">
            <div class="circuit">{e["circuit"]}</div>
            <div class="meta"><b>Datum:</b> {e["date"]}</div>
            <div class="meta"><b>Organisatie:</b> {e["organisatie"]}</div>
            <p><small>{e["raw"]}</small></p>
        </div>
        """

    html += """
    </body>
    </html>
    """

    return html


@app.get("/debug", response_class=HTMLResponse)
def debug():
    urls = [
        ("Intertrack", "https://www.inter-track.be"),
        ("Trackdays.be nl", "https://www.trackdays.be/nl"),
        ("Trackdays.be fr", "https://www.trackdays.be/fr"),
        ("Trackdays.be en", "https://www.trackdays.be/en"),
    ]

    html = "<h1>Debug websites</h1>"

    for name, url in urls:
        try:
            r = requests.get(url, headers=HEADERS, timeout=10)
            soup = BeautifulSoup(r.text, "html.parser")
            text = soup.get_text("\n").lower()

            mettet = "ja" if "mettet" in text else "nee"
            croix = "ja" if "croix" in text else "nee"

            html += f"""
            <h2>{name}</h2>
            <p>URL: {url}</p>
            <p>Status: {r.status_code}</p>
            <p>Mettet gevonden: {mettet}</p>
            <p>Croix gevonden: {croix}</p>
            """

        except Exception as e:
            html += f"<h2>{name}</h2><p>Fout: {e}</p>"

    return html
