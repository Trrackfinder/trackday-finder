from fastapi import FastAPI
from fastapi.responses import HTMLResponse
import requests

app = FastAPI()

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) "
        "Version/16.0 Mobile/15E148 Safari/604.1"
    )
}


@app.get("/", response_class=HTMLResponse)
def home():

    try:

        r = requests.get(
            "https://plantrackday.com/en/calendar",
            headers=HEADERS,
            timeout=10
        )

        text_preview = r.text[:500]

        return f"""

        <html>
        <body style="font-family:Arial; max-width:800px; margin:auto;">

        <h1>🏁 Trackday Finder</h1>

        <p>Status code: {r.status_code}</p>

        <h3>Preview:</h3>

        <pre style="white-space: pre-wrap;">
{text_preview}
        </pre>

        </body>
        </html>

        """

    except Exception as e:

        return f"Error: {e}"
