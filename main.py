from fastapi import FastAPI
from fastapi.responses import HTMLResponse
import requests
from bs4 import BeautifulSoup
import re

app = FastAPI()

HEADERS = {
    "User-Agent": "Mozilla/5.0"
}


def get_events():

    url = "https://www.inter-track.be"

    r = requests.get(url, headers=HEADERS, timeout=10)

    soup = BeautifulSoup(r.text, "html.parser")

    text = soup.get_text("\n")

    events = []

    seen = set()

    for line in text.splitlines():

        clean = line.strip()

        if not clean:
            continue

        lower = clean.lower()

        if "mettet" not in lower and "croix" not in lower:
            continue

        # datum zoeken
        date_match = re.search(r"\d{2}/\d{2}/\d{4}", clean)

        if not date_match:
            continue

        date = date_match.group()

        # circuit
        if "mettet" in lower:
            circuit = "Mettet"
        else:
            circuit = "Croix"

        # duplicates voorkomen
        key = f"{date}-{circuit}"

        if key in seen:
            continue

        seen.add(key)

        events.append({
            "date": date,
            "circuit": circuit,
            "organisatie": "Intertrack",
            "raw": clean
        })

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
        </div>
        """

    html += """
    </body>
    </html>
    """

    return html
