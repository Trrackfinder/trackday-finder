from fastapi import FastAPI
from fastapi.responses import HTMLResponse
import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime

app = FastAPI()

HEADERS = {"User-Agent": "Mozilla/5.0"}

MONTHS = {
    "jan": "01",
    "feb": "02",
    "mrt": "03",
    "mar": "03",
    "apr": "04",
    "mei": "05",
    "may": "05",
    "jun": "06",
    "jul": "07",
    "aug": "08",
    "sep": "09",
    "okt": "10",
    "oct": "10",
    "nov": "11",
    "dec": "12",
}


def get_intertrack_events():
    events = []
    seen = set()

    try:
        r = requests.get("https://www.inter-track.be", headers=HEADERS, timeout=10)
        soup = BeautifulSoup(r.text, "html.parser")
        text = soup.get_text("\n")

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
            lines = [line.strip() for line in soup.get_text("\n").splitlines() if line.strip()]

            current_month = None

            for i, line in enumerate(lines):
                lower = line.lower().replace(".", "")

                if lower in MONTHS:
                    current_month = MONTHS[lower]
                    continue

                if "track mettet" not in lower and "track croix" not in lower and lower not in ["mettet", "croix"]:
                    continue

                circuit = "Mettet" if "mettet" in lower else "Croix"

                day = None

                for previous in reversed(lines[max(0, i - 8):i]):
                    previous_clean = previous.strip().lower().replace(".", "")

                    if previous_clean in MONTHS:
                        current_month = MONTHS[previous_clean]

                    if previous_clean.isdigit():
                        day = previous_clean.zfill(2)
                        break

                if not day or not current_month:
                    continue

                date = f"{day}/{current_month}/2026"

                key = f"{date}-{circuit}-Trackdays.be"

                if key in seen:
                    continue

                seen.add(key)

                nearby = " ".join(lines[max(0, i - 5): i + 6])

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
