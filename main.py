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

        if "mettet" not in lower and "croix" not in lower:
            continue

        # datum zoeken
        date_match = re.search(r"\d{2}/\d{2}/\d{4}", clean)

        if date_match:
            date = date_match.group()
        else:
            date = "Onbekend"

        # circuit bepalen
        if "mettet" in lower:
            circuit = "Mettet"
        else:
            circuit = "Croix"

        events.append({
            "date": date,
            "circuit": circuit,
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

    html += f"""

<div class="card">

    <h2>{e['circuit']}</h2>

    <p><b> 📅 Datum:</b> {e['date']}</p>

    <p><b> 🏢 Organisatie:</b> {e['organisatie']}</p>

</div>

"""

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
