from fastapi import FastAPI
from fastapi.responses import HTMLResponse

app = FastAPI()

@app.get("/", response_class=HTMLResponse)
def home():
    return """
    <html>
        <head>
            <title>Trackday Finder</title>
        </head>
        <body>
            <h1>🏁 Trackday Finder</h1>
            <p>Je app werkt online 🎉</p>
        </body>
    </html>
