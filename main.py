from fastapi import FastAPI
from fastapi.responses import HTMLResponse

from playwright.sync_api import sync_playwright

app = FastAPI()


def get_events():

    events = []

    with sync_playwright() as p:

        browser = p.chromium.launch(headless=True)

        page = browser.new_page()

        page.goto("https://plantrackday.com/en/calendar")

        page.wait_for_timeout(5000)

        content = page.content()

        browser.close()

    lines = content.splitlines()

    for line in lines:

        lower = line.lower()

        if "mettet" in lower:

            events.append({
                "circuit": "Mettet",
                "tekst": line.strip()
            })

        elif "croix" in lower:

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
    <body style="font-family:Arial; max-width:800px; margin:auto;">

    <h1>🏁 Trackday Finder</h1>

    """

    for e in events:

        html += f"""

        <div style="
            border:1px solid #ddd;
            padding:10px;
            margin-bottom:10px;
            border-radius:8px;
        ">

        <b>{e['circuit']}</b><br>
        {e['tekst']}

        </div>

        """

    html += "</body></html>"

    return html
