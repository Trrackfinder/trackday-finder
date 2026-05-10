from fastapi import FastAPI
from fastapi.responses import HTMLResponse
import requests
from bs4 import BeautifulSoup
import re

app = FastAPI()

HEADERS = {
    "User-Agent": "Mozilla/5.0"
}


def extract_events_from_text(text, organisatie):
    events = []
    seen = set()

    for line in text.splitlines():
        clean = line.strip()
        lower = clean.lower()

        if "mettet" not in lower and "croix" not in lower:
            continue

        date_match = re.search(r"\d{2}/\d{2}/\d{4}", clean)

        if not date_match:
            continue

        date = date_match.group()
        circuit = "Mettet" if "mettet" in lower else "Croix"
        key = f"{date}-{circuit}-{organisatie}"

        if key in seen:
            continue

        seen.add(key)

        events.append({
            "date": date,
            "circuit": circuit,
            "organisatie": organisatie,
            "raw": clean
        })

    return events


def get_intertrack_events():
    url = "https://www.inter-track.be"

    try:
        r = requests.get(url, headers=HEADERS, timeout=10)
        soup = BeautifulSoup(r.text, "html.parser")
        return extract_events_from_text(soup.get_text("\n"), "Intertrack")
    except Exception as e:
        print("Intertrack fout:", e)
        return []


def get_trackdays_events():
    urls = [
        "https://www.trackdays.be",
        "https://www.trackdays.be/nl",
        "https://www.trackdays.be/fr",
        "https://www.trackdays.be/en",
        "https://www.trackdays.be/nl/kalender",
        "https://www.trackdays.be/en/calendar",
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


def get_events():
    events = []
    events += get_intertrack_events()
    events += get_trackdays_events()

    events.sort(key=lambda e: e["date"])
    return events


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
            }
        </style>
    </head>
    <body>
        <h1>Trackday Finder</h1>
    """

    if len(events) == 0:
        html += "<p>Geen events gevonden.</p>"

    for e in events:
        html += f"""
        <div class="card">
            <h2>{e["circuit"]}</h2>
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


@app.get("/debug", response_class=HTMLResponse)
def debug():
    urls = [
        ("Intertrack", "https://www.inter-track.be"),
        ("Trackdays.be home", "https://www.trackdays.be"),
        ("Trackdays.be nl", "https://www.trackdays.be/nl"),
        ("Trackdays.be fr", "https://www.trackdays.be/fr"),
        ("Trackdays.be en", "https://www.trackdays.be/en"),
        ("Trackdays.be nl kalender", "https://www.trackdays.be/nl/kalender"),
        ("Trackdays.be en calendar", "https://www.trackdays.be/en/calendar"),
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
