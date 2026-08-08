from fastapi import FastAPI, HTTPException
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
import string
import secrets
from database import SessionLocal
from models import URL

app = FastAPI()




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
    db = SessionLocal()

    short_code = generate_short_code()

    new_url = URL(
        short_code=short_code,
        original_url=request.url
    )

    db.add(new_url)
    db.commit()

    db.close()

    return {
        "short_url": short_code
    }


@app.get("/{short_code}")
def redirect_url(short_code: str):
    db = SessionLocal()

    url = db.query(URL).filter(URL.short_code == short_code).first()

    db.close()

    if url is None:
        raise HTTPException(
            status_code=404,
            detail="Short URL not found"
        )

    return RedirectResponse(url=url.original_url)