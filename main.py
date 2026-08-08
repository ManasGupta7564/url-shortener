from fastapi import FastAPI, HTTPException
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
import string
import secrets

app = FastAPI()

url_database = {}


class URLRequest(BaseModel):
    url: str


def generate_short_code(length=6):
    characters = string.ascii_letters + string.digits
    return ''.join(secrets.choice(characters) for _ in range(length))


@app.get("/")
def home():
    return {"message": "URL Shortener is running!"}


@app.post("/shorten")
def shorten_url(request: URLRequest):
    short_code = generate_short_code()

    url_database[short_code] = request.url

    return {
        "short_url": short_code
    }


@app.get("/{short_code}")
def redirect_url(short_code: str):
    original_url = url_database.get(short_code)

    if original_url is None:
        raise HTTPException(status_code=404, detail="Short URL not found")

    return RedirectResponse(url=original_url)