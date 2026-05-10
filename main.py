from fastapi import FastAPI
from fastapi.responses import HTMLResponse

app = FastAPI()

@app.get("/", response_class=HTMLResponse)
def home():
    return """
    <html>
    <body style="font-family:Arial">
    <h1 Trackday Finder</H1>
    <p>Server werkt succesvol </p>
    </body>
    </html>
    """
