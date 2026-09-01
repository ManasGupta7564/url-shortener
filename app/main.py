from fastapi import FastAPI, HTTPException, Depends,BackgroundTasks,Request
from fastapi.responses import RedirectResponse
from sqlalchemy import func
from pydantic import BaseModel
import string
import secrets
from app.database import SessionLocal, get_db
from app.models import URL,Click
from sqlalchemy.orm import Session
from app.redis_client import redis_client
from sqlalchemy.exc import IntegrityError
import json
from datetime import datetime, timedelta
from typing import Optional
app = FastAPI()




class URLRequest(BaseModel):
    url: str
    expires_in: Optional[int] = None

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

        expires_at = None

        if request.expires_in is not None:

            expires_at = datetime.now() + timedelta(

                seconds=request.expires_in

            )

        new_url = URL(
            short_code=short_code,
            original_url=request.url,
            expires_at=expires_at
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


@app.get("/analytics/{short_code}")
def get_analytics(
    short_code: str,
    db: Session = Depends(get_db)
):
    url = db.query(URL).filter(
        URL.short_code == short_code
    ).first()

    if url is None:
        raise HTTPException(
            status_code=404,
            detail="Short URL not found"
        )

    total_clicks = db.query(Click).filter(
        Click.url_id == url.id
    ).count()

    clicks_by_day = (
        db.query(
            func.date(Click.clicked_at).label("date"),
            func.count(Click.id).label("clicks")
        )
        .filter(Click.url_id == url.id)
        .group_by(func.date(Click.clicked_at))
        .order_by(func.date(Click.clicked_at))
        .all()
    )
    referrer_stats = (
    db.query(
        Click.referrer,
        func.count(Click.id).label("clicks")
    )
    .filter(
        Click.url_id == url.id,
        Click.referrer.isnot(None)
    )
    .group_by(Click.referrer)
    .order_by(func.count(Click.id).desc())
    .all()
    )
    top_referrers = [
    {
        "referrer": row.referrer,
        "clicks": row.clicks
    }
    for row in referrer_stats
    ]
    daily_clicks = [
        {
            "date": str(row.date),
            "clicks": row.clicks
        }
        for row in clicks_by_day
    ]
    user_agent_stats = (
    db.query(
        Click.user_agent,
        func.count(Click.id).label("clicks")
    )
    .filter(
        Click.url_id == url.id,
        Click.user_agent.isnot(None)
    )
    .group_by(Click.user_agent)
    .order_by(func.count(Click.id).desc())
    .all()
    )
    user_agents = [
    {
        "user_agent": row.user_agent,
        "clicks": row.clicks
    }
    for row in user_agent_stats
    ]

    return {
        "short_code": url.short_code,
        "total_clicks": total_clicks,
        "clicks_by_day": daily_clicks,
        "top_referrers": top_referrers,
        "user_agents": user_agents
    }

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

        if data.get("expires_at"):
            expires_at = datetime.fromisoformat(data["expires_at"])

            if datetime.now() > expires_at:
                redis_client.delete(short_code)

                raise HTTPException(
                    status_code=410,
                    detail="This short URL has expired"
                )

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
    if url.expires_at is not None:
        if datetime.now() > url.expires_at:
            raise HTTPException(
                status_code=410,
                detail="This short URL has expired"
            )
    # 3. Store URL data in Redis
    cache_data = {
        "url_id": url.id,
        "original_url": url.original_url,
        "expires_at": (
            url.expires_at.isoformat()
            if url.expires_at
            else None
        )
    }

    cache_ttl = 3600

    if url.expires_at is not None:
        remaining_seconds = int(
            (url.expires_at - datetime.now()).total_seconds()
        )

        cache_ttl = min(cache_ttl, remaining_seconds)

    redis_client.set(
        short_code,
        json.dumps(cache_data),
        ex=cache_ttl
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

