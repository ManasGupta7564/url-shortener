from fastapi import FastAPI, HTTPException, Depends,BackgroundTasks,Request
from fastapi.responses import RedirectResponse

from pydantic import BaseModel
import string
import secrets
from app.database import SessionLocal, get_db
from app.models import URL,Click
from sqlalchemy.orm import Session
from app.redis_client import redis_client
from sqlalchemy.exc import IntegrityError
import json
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

def record_click(
    url_id: int,
    referrer: str | None,
    user_agent: str | None
):
    db = SessionLocal()

    try:
        click = Click(
            url_id=url_id,
            referrer=referrer,
            user_agent=user_agent
        )

        db.add(click)
        db.commit()

    finally:
        db.close()

@app.get("/{short_code}")
def redirect_url(
    short_code: str,
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    # 1. Check Redis
    cached_data = redis_client.get(short_code)

    if cached_data:
        data = json.loads(cached_data)

        background_tasks.add_task(
            record_click,
            data["url_id"],
            request.headers.get("referer"),
            request.headers.get("user-agent")
        )

        return RedirectResponse(
            url=data["original_url"]
        )

    # 2. Redis MISS → PostgreSQL
    url = db.query(URL).filter(
        URL.short_code == short_code
    ).first()

    if url is None:
        raise HTTPException(
            status_code=404,
            detail="Short URL not found"
        )

    # 3. Store URL data in Redis
    cache_data = {
        "url_id": url.id,
        "original_url": url.original_url
    }

    redis_client.set(
        short_code,
        json.dumps(cache_data),
        ex=3600
    )

    # 4. Record analytics
    background_tasks.add_task(
        record_click,
        url.id,
        request.headers.get("referer"),
        request.headers.get("user-agent")
    )

    # 5. Redirect
    return RedirectResponse(
        url=url.original_url
    )