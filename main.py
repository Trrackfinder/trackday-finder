from fastapi import FastAPI
from fastapi.responses import HTMLResponse
import requests

app = FastAPI()

@app.get("/", response_class=HTMLResponse)
def home():

    try:

        r = requests.get("https://plantrackday.com")

        return f"""

        <html>
        <body style="font-family:Arial">

        <h1>🏁 Trackday Finder</h1>

        <p>Website bereikbaar ✅</p>

        <p>Status code: {r.status_code}</p>

        </body>
        </html>

        """

    except Exception as e:

        return f"Error: {e}"
