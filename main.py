from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()


class URLRequest(BaseModel):
    url: str


@app.get("/")
def home():
    return {"message": "URL Shortener is running!"}


@app.post("/shorten")
def shorten_url(request: URLRequest):
    return {
        "short_url": "abc123"
    }