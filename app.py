import re, time, asyncio
from urllib.parse import urlparse
from collections import defaultdict, deque
import httpx, yt_dlp
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

app = FastAPI()
ALLOWED = {"instagram.com", "www.instagram.com"}
HITS = defaultdict(deque)
LIMIT, WINDOW = 10, 60  # 10 requests per minute per IP

def rate_limit(request: Request):
    ip = request.headers.get("x-forwarded-for", request.client.host).split(",")[0].strip()
    q, now = HITS[ip], time.time()
    while q and now - q[0] > WINDOW:
        q.popleft()
    if len(q) >= LIMIT:
        raise HTTPException(429, "Too many requests. Please wait a minute and try again.")
    q.append(now)

def check_url(url: str) -> str:
    u = urlparse(url.strip())
    if u.scheme not in ("http", "https") or u.hostname not in ALLOWED:
        raise HTTPException(400, "Please paste a valid Instagram link.")
    if not re.search(r"/(p|reel|reels|tv)/", u.path):
        raise HTTPException(400, "This link is not a post or reel.")
    return u.geturl()

def extract(url: str) -> dict:
    opts = {"quiet": True, "skip_download": True, "noplaylist": True}
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            return ydl.extract_info(url, download=False)
    except Exception:
        raise HTTPException(404, "Could not fetch this video. It may be private, deleted, or Instagram blocked the request.")

class Req(BaseModel):
    url: str

@app.post("/api/info")
async def info(body: Req, request: Request):
    rate_limit(request)
    url = check_url(body.url)
    d = await asyncio.to_thread(extract, url)
    if not d.get("url") and not d.get("formats"):
        raise HTTPException(404, "No video found in this post.")
    return {"title": (d.get("title") or "Instagram video")[:120],
            "uploader": d.get("uploader"),
            "thumbnail": d.get("thumbnail"),
            "duration": d.get("duration")}

@app.get("/api/download")
async def download(url: str, request: Request):
    rate_limit(request)
    url = check_url(url)
    d = await asyncio.to_thread(extract, url)
    direct = d.get("url") or d["formats"][-1]["url"]
    client = httpx.AsyncClient(timeout=60, follow_redirects=True)
    resp = await client.send(client.build_request("GET", direct), stream=True)
    async def gen():
        try:
            async for chunk in resp.aiter_bytes(65536):
                yield chunk
        finally:
            await resp.aclose(); await client.aclose()
    name = re.sub(r"[^\w-]", "", d.get("id", "video")) or "video"
    return StreamingResponse(gen(), media_type="video/mp4",
        headers={"Content-Disposition": f'attachment; filename="instagram-{name}.mp4"'})

@app.get("/")
def home():
    return FileResponse("static/index.html")

app.mount("/", StaticFiles(directory="static"), name="static")
