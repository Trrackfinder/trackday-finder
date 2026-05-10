from fastapi import FastAPI
from fastapi.responses import HTMLResponse
import requests
from bs4 import BeautifulSoup

app = FastAPI()

HEADERS = {
    "User-Agent": "Mozilla/5.0"
}


def get_events():

    urls = [
        "https://inter-track.be/en/calendar",
        "https://trackdays.be/en/calendar"
    ]

    events = []

    for url in urls:

        try:
            r = requests.get(url, headers=HEADERS, timeout=10)

            soup = BeautifulSoup(r.text, "html.parser")

            text = soup.get_text("\n")

            for line in text.splitlines():

                line_lower = line.lower()

                if "mettet" in line_lower:
                    events.append({
                        "circuit": "Mettet",
                        "organisatie": url
                    })

                elif "croix" in line_lower:
                    events.append({
                        "circuit": "Croix",
                        "organisatie": url
                    })

        except Exception as e:
            print(e)

    return events
