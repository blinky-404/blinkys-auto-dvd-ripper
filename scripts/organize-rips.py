#!/usr/bin/env python3
# ============================================================================
# Blinky's Auto DVD Ripper v2.0 - Media Audit, Identification & Organizer
# Pipeline: FFprobe Audio Audit -> Quality/Runtime Routing -> TMDB -> Local AI Vision
# ============================================================================
import os, re, sys, json, time, base64, shutil, subprocess, urllib.request, urllib.parse
from datetime import datetime

SYSTEM_DIR = os.environ.get("SYSTEM_DIR", "/DATA/ripper_system")
MEDIA_DIR = os.environ.get("MEDIA_DIR", "/DATA/ripper_media")
CONF_FILE = os.path.join(SYSTEM_DIR, "config", "organizer.conf")
LOG_FILE = os.path.join(SYSTEM_DIR, "logs", "organizer.log")

os.makedirs(os.path.join(SYSTEM_DIR, "logs"), exist_ok=True)
for sub in ["finished", "organized_movies", "low_quality_quarantine", "no_audio"]:
    os.makedirs(os.path.join(MEDIA_DIR, sub), exist_ok=True)

def load_conf():
    cfg = {
        "IDENTIFY_MODE": "db_then_ai", "PRIMARY_DB": "tmdb", "TMDB_TOKEN": "",
        "ENABLE_UNMATCHED_SNAPSHOTS": "true", "AI_PROVIDER": "local_ollama",
        "LOCAL_AI_MODEL": "moondream", "AI_API_KEY": "",
        "ENABLE_SILENT_QUARANTINE": "true", "ENABLE_RUNTIME_CHECK": "true",
        "MIN_RUNTIME_MINS": "45", "ENABLE_QUALITY_SORT": "true",
        "MIN_VIDEO_HEIGHT": "300", "MIN_VIDEO_BITRATE_KBPS": "400",
        "SAVE_MOVIE_INFO_TXT": "true", "LOG_MAX_LINES": "500",
    }
    if os.path.exists(CONF_FILE):
        with open(CONF_FILE) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                cfg[k.strip()] = v.strip().strip('"').strip("'")
    return cfg

CFG = load_conf()
MAX_LINES = int(CFG.get("LOG_MAX_LINES", 500))

def log(msg):
    line = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}\n"
    print(line, end="")
    lines = []
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE) as f:
            lines = f.readlines()
    lines.append(line)
    with open(LOG_FILE, "w") as f:
        f.writelines(lines[-MAX_LINES:])


# Inspect video resolution, runtime, and audio codecs using ffprobe
def probe_media(filepath):
    cmd = ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", "-show_streams", filepath]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        return None
    data = json.loads(res.stdout)
    dur = float(data.get("format", {}).get("duration", 0))
    br = int(data.get("format", {}).get("bit_rate", 0)) // 1000
    vs = next((s for s in data.get("streams", []) if s.get("codec_type") == "video"), None)
    aus = [s for s in data.get("streams", []) if s.get("codec_type") == "audio"]
    if not vs:
        return None
    return {
        "duration_mins": round(dur / 60.0, 1), "duration_secs": dur, "bitrate_kbps": br,
        "width": int(vs.get("width", 0)), "height": int(vs.get("height", 0)),
        "v_codec": vs.get("codec_name", "unknown"),
        "a_codecs": [f"{s.get('codec_name')}({s.get('channels')}ch)" for s in aus]
    }

def create_snapshot_grid(filepath, out_jpg, duration_secs):
    if duration_secs < 4:
        subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", filepath, "-vframes", "1", out_jpg])
        return os.path.exists(out_jpg)
    tmp_dir = f"/tmp/snap_{int(time.time()*1000)}"
    os.makedirs(tmp_dir, exist_ok=True)
    frames = []
    for idx, pct in enumerate([0.15, 0.38, 0.62, 0.85]):
        ts = max(1, int(duration_secs * pct))
        fp = os.path.join(tmp_dir, f"f{idx}.jpg")
        subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-ss", str(ts), "-i", filepath, "-vframes", "1", "-vf", "scale=480:-1", fp])
        if os.path.exists(fp):
            frames.append(fp)
    if len(frames) == 4:
        subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", frames[0], "-i", frames[1], "-i", frames[2], "-i", frames[3], "-filter_complex", "hstack=inputs=2[top];[2:v][3:v]hstack=inputs=2[bot];[top][bot]vstack=inputs=2", out_jpg])
    elif frames:
        shutil.copy(frames[0], out_jpg)
    shutil.rmtree(tmp_dir, ignore_errors=True)
    return os.path.exists(out_jpg)

def clean_disc_name(filename):
    base = os.path.splitext(filename)[0]
    base = re.sub(r'[-_](title|t)\d+$', '', base, flags=re.I)
    base = re.sub(r'^[A-Z]\d+_', '', base)
    base = re.sub(r'[-_][a-zA-Z0-9]{6}$', '', base)
    return re.sub(r'[._-]+', ' ', base).strip()

# Query The Movie Database (TMDB) API for canonical title & release year
def lookup_tmdb(query, token):
    if not token:
        return None
    url = "https://api.themoviedb.org/3/search/multi?query=" + urllib.parse.quote(query)
    req = urllib.request.Request(url, headers={"Authorization": "Bearer " + token, "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            for r in json.loads(resp.read().decode()).get("results", []):
                if r.get("media_type") in ("movie", "tv"):
                    title = r.get("title") or r.get("name")
                    date = r.get("release_date") or r.get("first_air_date") or ""
                    yr = date[:4] if len(date) >= 4 else ""
                    return f"{title} ({yr})" if yr else title
    except Exception as e:
        log(f"   -> TMDB lookup error: {e}")
    return None

def lookup_tvmaze(query):
    url = "https://://tvmaze.com" + urllib.parse.quote(query)
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            data = json.loads(resp.read().decode())
            name = data.get("name")
            yr = (data.get("premiered") or "")[:4]
            if name:
                return f"{name} ({yr})" if yr else name
    except Exception:
        pass
    return None

def lookup_musicbrainz(query):
    url = "https://musicbrainz.org/ws/2/release/?query=" + urllib.parse.quote(query) + "&fmt=json&limit=1"
    req = urllib.request.Request(url, headers={"User-Agent": "BlinkysAutoDVDRipper/2.0 (blinky-404)"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            releases = json.loads(resp.read().decode()).get("releases", [])
            if releases:
                rel = releases[0]
                title = rel.get("title", "")
                artist = rel.get("artist-credit", [{}])[0].get("name", "")
                yr = (rel.get("date") or "")[:4]
                label = f"{artist} - {title}" if artist else title
                return f"{label} ({yr})" if yr else label
    except Exception:
        pass
    return None

def query_database(query):
    db = CFG.get("PRIMARY_DB", "tmdb")
    if db == "tmdb":
        return lookup_tmdb(query, CFG.get("TMDB_TOKEN", ""))
    elif db == "tvmaze":
        return lookup_tvmaze(query)
    elif db == "musicbrainz":
        return lookup_musicbrainz(query)
    return None

# Fallback: capture a 2x2 frame grid and query Local Ollama (moondream) or Cloud AI
def identify_with_ai(grid_jpg):
    provider = CFG.get("AI_PROVIDER", "local_ollama")
    prompt = "Identify the movie, TV show, or concert shown in these video frames. Reply ONLY with the exact title and release year in the format: Title (Year). If unrecognizable, reply UNKNOWN."
    with open(grid_jpg, "rb") as f:
        b64_img = base64.b64encode(f.read()).decode()

    if provider == "local_ollama":
        model = CFG.get("LOCAL_AI_MODEL", "moondream")
        obin = "/DATA/ripper_system/ollama/bin/ollama"
        env = dict(os.environ, OLLAMA_MODELS="/DATA/ripper_system/ollama/models", OLLAMA_HOST="127.0.0.1:11434")
        srv = subprocess.Popen([obin, "serve"], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) if os.path.exists(obin) else None
        if not srv: subprocess.run(["docker", "start", "ripper-ai-vision"], capture_output=True)
        time.sleep(3)
        try:
            for _ in range(15):
                try:
                    urllib.request.urlopen("http://127.0.0", timeout=1)
                    break
                except Exception:
                    time.sleep(0.5)
            payload = json.dumps({"model": model, "messages": [{"role": "user", "content": prompt, "images": [b64_img]}], "stream": False}).encode()
            req = urllib.request.Request("http://127.0.0api/chat", data=payload, headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=120) as resp:
                ans = (lambda d: d.get("response") or d.get("message", {}).get("content", ""))(json.loads(resp.read().decode())).strip()
                if ans and "UNKNOWN" not in ans.upper():
                    return re.sub(r'[\\/:*?"<>|]', '', ans).strip()
        except Exception as ex:
            log(f"   -> Local Ollama Vision error: {ex}")
        finally:
            if srv: srv.terminate(); srv.wait(timeout=5)
            else: subprocess.run(["docker", "stop", "ripper-ai-vision"], capture_output=True)
    elif provider == "gemini" and CFG.get("AI_API_KEY"):
        url = "https://://googleapis.com" + CFG["AI_API_KEY"]
        payload = json.dumps({"contents": [{"parts": [{"text": prompt}, {"inline_data": {"mime_type": "image/jpeg", "data": b64_img}}]}]}).encode()
        req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode())
                ans = data["candidates"]["content"]["parts"]["text"].strip()
                if ans and "UNKNOWN" not in ans.upper():
                    return re.sub(r'[\\/:*?"<>|]', '', ans).strip()
        except Exception as e:
            log(f"   -> Gemini Vision error: {e}")
    return None

def process_finished():
    fin_dir = os.path.join(MEDIA_DIR, "finished")
    files = [os.path.join(r, fn) for r, _, fns in os.walk(fin_dir) for fn in fns if fn.lower().endswith((".mp4", ".mkv", ".m4v")) and not fn.startswith(".")]
    if not files:
        log("Organizer check complete: No new files in finished/.")
        return
    for fpath in sorted(files):
        fname = os.path.basename(fpath)
        log(f"Processing: {fname}")
        info = probe_media(fpath)
        if not info:
            log(f"   -> ERROR: Could not read streams for {fname}; skipping.")
            continue
        stem, ext = os.path.splitext(fname)
        if not info["a_codecs"] and CFG.get("ENABLE_SILENT_QUARANTINE") == "true":
            shutil.move(fpath, os.path.join(MEDIA_DIR, "no_audio", f"{stem}_NO_AUDIO{ext}"))
            log("   -> QUARANTINED to no_audio/ (0 audio streams)")
            continue
        min_mins = float(CFG.get("MIN_RUNTIME_MINS", 45))
        is_short = (CFG.get("ENABLE_RUNTIME_CHECK") == "true" and info["duration_mins"] < min_mins)
        mode, query = CFG.get("IDENTIFY_MODE", "db_then_ai"), re.sub(r"(\s*\(Unmatched\)|_SHORT_\d+m|\b(special|director.?s|extended|unrated|widescreen|fullscreen|collector.?s|anniversary|remastered|deluxe|theatrical|blu-?ray|dvd)\s*(edition|cut|version)?\b|\bt\d+\b|\b[A-Z]\d+\b)", "", clean_disc_name(fname), flags=re.I).strip()
        if len(query) <= 3: query = ""
        matched = query_database(query) if mode in ("db_only", "db_then_ai") and query.upper() not in ("DVD VIDEO", "DISC 1", "DISC 2", "VIDEO TS", "MOVIE") else None
        tmp_snap, has_snap = f"/tmp/grid_{int(time.time()*1000)}.jpg", False
        if not matched and mode in ("ai_only", "db_then_ai"):
            has_snap = create_snapshot_grid(fpath, tmp_snap, info["duration_secs"])
            guess = identify_with_ai(tmp_snap) if has_snap else None
            if guess:
                matched = query_database(re.sub(r'\(\d{4}\)', '', guess).strip()) or guess
        if not matched:
            matched = f"{query or 'Unknown Disc'} (Unmatched)"
            if not has_snap and CFG.get("ENABLE_UNMATCHED_SNAPSHOTS") == "true":
                has_snap = create_snapshot_grid(fpath, tmp_snap, info["duration_secs"])
        safe = re.sub(r'[\\/:*?"<>|]', '', matched).strip()
        is_low, reasons = False, []
        if CFG.get("ENABLE_QUALITY_SORT") == "true":
            if info["height"] < int(CFG.get("MIN_VIDEO_HEIGHT", 300)):
                is_low, reasons = True, reasons + [f"Height {info['height']}p"]
            if 0 < info["bitrate_kbps"] < int(CFG.get("MIN_VIDEO_BITRATE_KBPS", 400)):
                is_low, reasons = True, reasons + [f"Bitrate {info['bitrate_kbps']}kbps"]
        base_bucket = "short_videos" if is_short else ("low_quality_quarantine" if is_low else "organized_movies")
        dest_dir = os.path.join(MEDIA_DIR, base_bucket, safe)
        os.makedirs(dest_dir, exist_ok=True)
        shutil.move(fpath, os.path.join(dest_dir, f"{safe} - Extra ({info['duration_mins']}m){ext}" if is_short else f"{safe}{ext}"))
        for r_root, _, r_files in os.walk(os.path.join(MEDIA_DIR, "raw")):
            if f"{stem}.mkv" in r_files:
                os.remove(os.path.join(r_root, f"{stem}.mkv"))
                if not os.listdir(r_root) and r_root != os.path.join(MEDIA_DIR, "raw"):
                    os.rmdir(r_root)
        if has_snap and os.path.exists(tmp_snap):
            shutil.move(tmp_snap, os.path.join(dest_dir, "preview_grid.jpg")) if "(Unmatched)" in safe else os.remove(tmp_snap)
        if CFG.get("SAVE_MOVIE_INFO_TXT") == "true":
            with open(os.path.join(dest_dir, f"{safe}_info.txt"), "w") as tf:
                tf.write(f"Title: {safe}\nSource: {fname}\nStatus: {'LOW QUALITY' if is_low else 'FULL QUALITY'}\nResolution: {info['width']}x{info['height']} ({info['v_codec']})\nBitrate: {info['bitrate_kbps']} kbps\nRuntime: {info['duration_mins']} mins\nAudio: {', '.join(info['a_codecs']) or 'NONE'}\n")
        log(f"   -> Routed to {base_bucket}/{safe}/")

if __name__ == "__main__":
    process_finished()
