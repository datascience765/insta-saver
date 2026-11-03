# Instagram Video Downloader

## Run locally
    pip install -r requirements.txt
    uvicorn app:app --reload
Open http://localhost:8000

## Deploy (Railway / Render / VPS)
Start command: `uvicorn app:app --host 0.0.0.0 --port $PORT`
Update yt-dlp often: `pip install -U yt-dlp` (Instagram changes break it).

## Before launch
- Replace contact@yourdomain.com in static/index.html
- Put the site behind Cloudflare; keep the rate limit in app.py
- Add a proper Privacy and Terms page
