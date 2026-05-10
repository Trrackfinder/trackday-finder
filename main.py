from fastapi import FastAPI
from fastapi.responses import HTMLResponse
import requests
from bs4 import BeautifulSoup

app = FastAPI()

HEADERS = {
    "User-Agent": "Mozilla/5.0"
}


def get_events():

    url = "https://plantrackday.com/en/calendar"

    r = requests.get(url, headers=HEADERS)

    soup = BeautifulSoup(r.text, "html.parser")

    text = soup.get_text("\n")

    events = []

    for line in text.splitlines():

        line_lower = line.lower().strip()

        if "mettet" in line_lower:

            events.append({
                "circuit": "Mettet",
                "tekst": line.strip()
            })

        elif "croix" in line_lower:

            events.append({
                "circuit": "Croix",
                "tekst": line.strip()
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
            max-width: 800px;
            margin: auto;
            padding: 20px;
        }

        .card {
            border: 1px solid #ddd;
            border-radius: 8px;
            padding: 10px;
            margin-bottom: 10px;
        }

        </style>

    </head>

    <body>

    <h1>🏁 Trackday Finder</h1>

    """

    for e in events:

        html += f"""

        <div class="card">

            <b>{e['circuit']}</b><br>
            {e['tekst']}

        </div>

        """

    html += "</body></html>"

    return html
