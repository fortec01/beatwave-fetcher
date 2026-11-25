"""BeatWave fetcher — resolves a song (title+artist) to a YouTube match and
streams the full audio through this service. Personal use, single user.

Endpoints (all require ?k=<FETCH_KEY> when FETCH_KEY is set):
  GET /health
  GET /resolve?title=&artist=&duration=  -> JSON match info
  GET /stream?id=<videoId>              -> audio bytes (Range supported)
  GET /play?title=&artist=&duration=    -> 302 to /stream?id=...
"""
import os
import socket
import time
import threading

import requests
from flask import Flask, request, jsonify, Response, redirect, abort

import yt_dlp

app = Flask(__name__)
KEY = os.environ.get("FETCH_KEY", "")

# Cloudflare WARP egress (wireproxy, started by start.sh): YouTube flags
# this host's own datacenter IPs, so extraction + streaming go through the
# local SOCKS5 proxy when it is up.
PROXY = os.environ.get("YT_PROXY", "socks5h://127.0.0.1:1080")
_proxy_state = {"checked": False, "on": False}


def proxy_on():
    if not _proxy_state["checked"]:
        try:
            s = socket.socket()
            s.settimeout(1)
            _proxy_state["on"] = s.connect_ex(("127.0.0.1", 1080)) == 0
            s.close()
        except OSError:
            _proxy_state["on"] = False
        _proxy_state["checked"] = True
    return _proxy_state["on"]


def req_proxies():
    return {"http": PROXY, "https": PROXY} if proxy_on() else None

_cache = {}          # videoId -> (expires, stream_url, content_type)
_cache_lock = threading.Lock()
CACHE_TTL = 4 * 3600  # googlevideo URLs live ~6h; stay safely under


def check_key():
    if KEY and request.args.get("k") != KEY:
        abort(403)


def ydl_opts(**extra):
    opts = {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "socket_timeout": 20,
        # PO-token support: the bgutil plugin (installed via pip) mints a
        # per-video proof-of-origin token using Node; needed to get past
        # YouTube's bot wall from datacenter IPs.
        "js_runtimes": {"node": {}},
        "remote_components": ["ejs:github"],
    }
    if proxy_on():
        opts["proxy"] = PROXY
    opts.update(extra)
    return opts


# Client strategies, best first. The first pairs the PO-token plugin with the
# clients the yt-dlp community currently finds working from cloud IPs.
CLIENT_STRATEGIES = [
    ["web", "android_vr", "tv_downgraded"],
    ["android_vr"],
    ["android", "ios"],
    None,
]

# The bgutil token script lives inside the project dir (built by
# setup_pot.sh); point the plugin at it explicitly instead of relying on
# its $HOME default, which Render does not carry into the runtime.
POT_SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          "vendor", "bgutil", "server", "build",
                          "generate_once.js")


def strategy_extra(clients, **base):
    extra = dict(base)
    ea = {"youtubepot-bgutilscript": {"script_path": [POT_SCRIPT]}}
    if clients:
        ea["youtube"] = {"player_client": clients}
    extra["extractor_args"] = ea
    return extra


def score_candidate(cand, want_dur):
    dur = cand.get("duration") or 0
    if want_dur:
        diff = abs(dur - want_dur)
        if diff > 45:
            return -1
        return 1000 - diff * 10
    return dur


def resolve(title, artist, want_dur):
    query = f"{title} {artist}".strip()
    search = f"ytsearch5:{query}"
    last_err = None
    for clients in CLIENT_STRATEGIES:
        extra = strategy_extra(clients)
        try:
            with yt_dlp.YoutubeDL(ydl_opts(**extra)) as ydl:
                info = ydl.extract_info(search, download=False)
            entries = [e for e in (info.get("entries") or []) if e]
            if not entries:
                continue
            best, best_score = None, -2
            for e in entries:
                s = score_candidate(e, want_dur)
                if s > best_score:
                    best, best_score = e, s
            if best is not None and best_score > -1:
                return {
                    "videoId": best.get("id"),
                    "title": best.get("title"),
                    "duration": best.get("duration"),
                    "uploader": best.get("uploader"),
                }
        except Exception as e:  # noqa: BLE001 - report and try next client
            last_err = e
    raise RuntimeError(f"resolve failed: {last_err}")


def get_stream_url(video_id):
    now = time.time()
    with _cache_lock:
        hit = _cache.get(video_id)
        if hit and hit[0] > now:
            return hit[1], hit[2]
    url = f"https://www.youtube.com/watch?v={video_id}"
    last_err = None
    for clients in CLIENT_STRATEGIES:
        extra = strategy_extra(clients, format="bestaudio/best")
        try:
            with yt_dlp.YoutubeDL(ydl_opts(**extra)) as ydl:
                info = ydl.extract_info(url, download=False)
            fmts = [f for f in (info.get("formats") or [])
                    if f.get("acodec") not in (None, "none") and f.get("url")]
            if not fmts:
                if info.get("url"):
                    fmts = [info]
                else:
                    continue
            fmts.sort(key=lambda f: (f.get("abr") or 0))
            chosen = fmts[-1]
            stream_url = chosen["url"]
            ctype = "audio/mp4" if "mp4" in (chosen.get("ext") or "") or (chosen.get("acodec") or "").startswith("mp4a") else "audio/webm"
            with _cache_lock:
                _cache[video_id] = (now + CACHE_TTL, stream_url, ctype)
            return stream_url, ctype
        except Exception as e:  # noqa: BLE001
            last_err = e
    raise RuntimeError(f"stream resolve failed: {last_err}")


@app.get("/health")
def health():
    return jsonify({"ok": True, "service": "beatwave-fetcher"})


@app.get("/resolve")
def resolve_ep():
    check_key()
    title = request.args.get("title", "")
    artist = request.args.get("artist", "")
    dur = request.args.get("duration", type=int)
    if not title:
        return jsonify({"error": "title required"}), 400
    try:
        return jsonify(resolve(title, artist, dur))
    except Exception as e:  # noqa: BLE001
        return jsonify({"error": str(e)[:300]}), 502


@app.get("/play")
def play_ep():
    check_key()
    title = request.args.get("title", "")
    artist = request.args.get("artist", "")
    dur = request.args.get("duration", type=int)
    if not title:
        return jsonify({"error": "title required"}), 400
    try:
        match = resolve(title, artist, dur)
    except Exception as e:  # noqa: BLE001
        return jsonify({"error": str(e)[:300]}), 502
    q = f"?id={match['videoId']}"
    if KEY:
        q += f"&k={KEY}"
    return redirect(f"/stream{q}", code=302)


@app.get("/stream")
def stream_ep():
    check_key()
    video_id = request.args.get("id", "")
    if not video_id:
        return jsonify({"error": "id required"}), 400
    try:
        stream_url, ctype = get_stream_url(video_id)
    except Exception as e:  # noqa: BLE001
        return jsonify({"error": str(e)[:300]}), 502

    headers = {}
    range_hdr = request.headers.get("Range")
    if range_hdr:
        headers["Range"] = range_hdr
    upstream = requests.get(stream_url, headers=headers, stream=True, timeout=30,
                            proxies=req_proxies())

    resp_headers = {
        "Content-Type": ctype,
        "Accept-Ranges": "bytes",
        "Cache-Control": "no-store",
    }
    for h in ("Content-Length", "Content-Range"):
        if upstream.headers.get(h):
            resp_headers[h] = upstream.headers[h]

    def gen():
        try:
            for chunk in upstream.iter_content(chunk_size=65536):
                if chunk:
                    yield chunk
        finally:
            upstream.close()

    return Response(gen(), status=upstream.status_code, headers=resp_headers)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "10000")))
