from fastapi import FastAPI, HTTPException, Depends
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
import string
import secrets
from app.database import SessionLocal, get_db
from app.models import URL
from sqlalchemy.orm import Session
from app.redis_client import redis_client
from sqlalchemy.exc import IntegrityError

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
def shorten_url(
    request: URLRequest,
    db: Session = Depends(get_db)
):
    while True:
        short_code = generate_short_code()

        new_url = URL(
            short_code=short_code,
            original_url=request.url
        )

        db.add(new_url)

        try:
            db.commit()
            break

        except IntegrityError:
            db.rollback()

    return {
        "short_url": short_code
    }

@app.get("/{short_code}")
def redirect_url(
    short_code: str,
    db: Session = Depends(get_db)
):
    # 1. Check Redis
    cached_url = redis_client.get(short_code)

    if cached_url:
        return RedirectResponse(url=cached_url)

    # 2. Cache miss → check PostgreSQL
    url = db.query(URL).filter(
        URL.short_code == short_code
    ).first()

    if url is None:
        raise HTTPException(
            status_code=404,
            detail="Short URL not found"
        )

    # 3. Store the result in Redis
    redis_client.set(
    short_code,
    url.original_url,
    ex=3600
)

    # 4. Redirect
    return RedirectResponse(url=url.original_url)