from fastapi import FastAPI
from fastapi.responses import HTMLResponse
import requests
from bs4 import BeautifulSoup

app = FastAPI()

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) "
        "Version/16.0 Mobile/15E148 Safari/604.1"
    )
}


def get_events():

    url = "https://www.inter-track.be"

    r = requests.get(
        url,
        headers=HEADERS,
        timeout=10
    )

    soup = BeautifulSoup(r.text, "html.parser")

    text = soup.get_text("\n")

    events = []

    for line in text.splitlines():

        clean = line.strip()

        if not clean:
            continue

        lower = clean.lower()

        if "mettet" in lower:

            events.append({
                "circuit": "Mettet",
                "tekst": clean,
                "organisatie": "Intertrack"
            })

        elif "croix" in lower:

            events.append({
                "circuit": "Croix",
                "tekst": clean,
                "organisatie": "Intertrack"
            })

    return events


@app.get("/", response_class=HTMLResponse)
def home():

    events = get_events()

    html = """

    <html>

    <head>

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

    <h1>🏁 Trackday Finder</h1>

    """

    if len(events) == 0:

        html += "<p>Geen events gevonden.</p>"

    for e in events:

        html += f"""

        <div class="card">

            <h3>{e['circuit']}</h3>

            <p>{e['organisatie']}</p>

            <p>{e['tekst']}</p>

        </div>

        """

    html += "</body></html>"

    return html
