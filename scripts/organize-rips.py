"""Blinky's Auto DVD Ripper — Media Organizer & AI Identification Pipeline.

Stages:
  1. Quarantine & Audio Audit (short tracks < 45m -> short_videos/, missing audio -> no_audio/)
  2. Disc Title Resolution (parent folder / raw/<DISC_FOLDER> lookup, skipping generic names)
  3. TMDB Metadata Matching (strips edition/year tags before querying)
  4. CPU-Gated AI Queue (parks unidentified rips in ai_hold/ while CPU >= 70%)
  5. Progressive Ollama Vision + Dual-Model Consensus + TMDB Runtime Guard (+/- 6m)
  6. Routing to organized_movies/ or short_videos/, saving _AI_preview.jpg & pruning raw/
"""
#!/usr/bin/env python3
# ============================================================================
# Blinky's Auto DVD Ripper v2.0 - Media Audit, Identification & Organizer
# Pipeline: FFprobe Audio Audit -> Quality/Runtime Routing -> TMDB -> Local AI Vision
# ============================================================================
import os, fcntl, re, sys, json, time, base64, shutil, subprocess, urllib.request, urllib.parse
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
        "LOCAL_AI_MODEL": "gemma3:4b", "AI_API_KEY": "",
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
def _http_get_json(url, headers=None, timeout=10):
    cmd = ["curl", "-sS", "--max-time", str(timeout)]
    for k, v in (headers or {}).items():
        cmd += ["-H", f"{k}: {v}"]
    cmd.append(url)
    res = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return json.loads(res.stdout)

def _tmdb_runtime_mins(media_type, item_id, token):
    try:
        u = "https://themoviedb.org" + str(media_type) + "/" + str(item_id)
        d = _http_get_json(u, {"Authorization": "Bearer " + token, "Accept": "application/json"}, 8)
        if media_type == "movie":
            return int(d.get("runtime") or 0)
        eps = d.get("episode_run_time") or []
        return int(eps[0]) if eps else 0
    except Exception:
        return 0

def lookup_tmdb(query, token, duration_mins=0):
    if not token:
        return None
    url = "https://themoviedb.orgsearch/multi?include_adult=false&language=en-US&query=" + urllib.parse.quote(query)
    try:
        candidates = [r for r in _http_get_json(url, {"Authorization": "Bearer " + token, "Accept": "application/json"}, 10).get("results", []) if r.get("media_type") in ("movie", "tv")][:8]
        if not candidates:
            return None
        def score(r):
            s = float(r.get("popularity") or 0)
            if r.get("original_language") == "en":
                s += 100.0
            else:
                s -= 50.0
            if int(r.get("vote_count") or 0) >= 20:
                s += 40.0
            if r.get("media_type") == "movie" and duration_mins >= 65:
                s += 25.0
            return s
        candidates.sort(key=score, reverse=True)
        for r in candidates:
            mtype = r.get("media_type")
            mid = r.get("id")
            title = r.get("title") or r.get("name")
            date = r.get("release_date") or r.get("first_air_date") or ""
            yr = date[:4] if len(date) >= 4 else ""
            if duration_mins > 0 and mid:
                rt = _tmdb_runtime_mins(mtype, mid, token)
                if rt > 0 and abs(rt - duration_mins) > 8:
                    log(f"   -> TMDB candidate rejected by runtime guard: {title} ({yr}) is {rt}m vs disc {duration_mins}m")
                    continue
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
GENERIC_DISC_NAMES = {"dvd", "dvd_video", "video_ts", "bdmv", "disc", "disc1", "disc2", "disk", "untitled", "unknown", "unidentified", "volume", "movie", "video", "main", "finished", "ai_hold"}

def is_generic_name(name):
    cleaned = re.sub(r"[\s_\-]+", "_", (name or "").strip().lower()).strip("_")
    return not cleaned or cleaned in GENERIC_DISC_NAMES or bool(re.fullmatch(r"(disc|disk|dvd|title|track|volume)_?\d*", cleaned))

def resolve_source_title(fpath, fname):
    stem, _ = os.path.splitext(fname)
    parent = os.path.basename(os.path.dirname(fpath))
    if not is_generic_name(parent):
        return parent
    raw_root = os.path.join(MEDIA_DIR, "raw")
    for r, _, r_files in os.walk(raw_root):
        if f"{stem}.mkv" in r_files and os.path.abspath(r) != os.path.abspath(raw_root):
            raw_folder = os.path.basename(r)
            if not is_generic_name(raw_folder):
                return raw_folder
    return fname

def pick_secondary_ollama_model(primary_model):
    chosen = CFG.get("SECONDARY_AI_MODEL", "moondream").strip()
    if not chosen or chosen.lower() == "none" or chosen == primary_model:
        return None
    mdir = "/DATA/ripper_system/ollama/models/manifests/registry.ollama.ai/library"
    if not os.path.isdir(mdir):
        return None
    base = chosen.partition(":").__getitem__(0)
    return chosen if base in os.listdir(mdir) else None

def current_cpu_pct():
    try:
        load1 = os.getloadavg().__getitem__(0)
        cores = os.cpu_count() or 1
        return round(min(100.0, (load1 / cores) * 100.0), 1)
    except Exception:
        return 0.0

def identify_with_ai(video_path, duration_secs, out_dir):
    provider = CFG.get("AI_PROVIDER", "none")
    if provider == "none":
        return None
    os.makedirs(out_dir, exist_ok=True)
    # Progressive snapshot batches (up to 30 frames total: opening credits -> mid-film -> end credits)
    batches = [
        [0.02, 0.05, 0.10, 0.18],
        [0.01, 0.03, 0.07, 0.12, 0.25, 0.35],
        [0.42, 0.50, 0.58, 0.66, 0.74, 0.82],
        [0.88, 0.91, 0.93, 0.95, 0.97, 0.99],
        [0.015, 0.04, 0.15, 0.30, 0.70, 0.94],
    ]
    prompt = "Identify the exact movie, TV show, or concert title shown in these video frames (check any title cards, credits, actors, or logos). Reply ONLY with the clean title (and year if known). If completely unrecognizable, reply UNKNOWN."
    obin = "/DATA/ripper_system/ollama/bin/ollama"
    model = CFG.get("LOCAL_AI_MODEL", "gemma3:4b")
    env = dict(os.environ, OLLAMA_MODELS="/DATA/ripper_system/ollama/models", OLLAMA_HOST="127.0.0.1:11434")
    srv = None
    if provider == "local_ollama" and os.path.exists(obin):
        srv = subprocess.Popen([obin, "serve"], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(15):
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{11434}/", timeout=1)
                break
            except Exception:
                time.sleep(0.5)
    try:
        total_snaps = 0
        for b_idx, pcts in enumerate(batches):
            frames = []
            for idx, pct in enumerate(pcts):
                ts = max(2, int(duration_secs * pct))
                f_out = os.path.join(out_dir, f"_frame_{b_idx}_{idx}.jpg")
                subprocess.run(["ffmpeg", "-y", "-ss", str(ts), "-i", video_path, "-vframes", "1", "-q:v", "4", f_out], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                if os.path.exists(f_out):
                    frames.append(f_out)
            if not frames:
                continue
            total_snaps += len(frames)
            cols = 2 if len(frames) <= 4 else 3
            rows = (len(frames) + cols - 1) // cols
            grid_path = os.path.join(out_dir, "preview_grid.jpg")
            subprocess.run(["ffmpeg", "-y", "-pattern_type", "glob", "-i", os.path.join(out_dir, f"_frame_{b_idx}_*.jpg"), "-filter_complex", f"scale=480:-1,tile={cols}x{rows}", grid_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            for f in frames:
                try: os.remove(f)
                except OSError: pass
            if not os.path.exists(grid_path):
                continue

            ans = ""
            if provider == "local_ollama":
                with open(grid_path, "rb") as gf:
                    b64_img = base64.b64encode(gf.read()).decode()
                payload = json.dumps({"model": model, "prompt": prompt, "images": [b64_img], "stream": False, "keep_alive": "5m", "options": {"num_predict": 32, "temperature": 0.1}}).encode()
                req = urllib.request.Request(f"http://127.0.0.1:{11434}/api/generate", data=payload, headers={"Content-Type": "application/json"})
                with urllib.request.urlopen(req, timeout=300) as resp:
                    ans = json.loads(resp.read().decode()).get("response", "").strip()
            elif provider == "gemini" and CFG.get("GEMINI_API_KEY"):
                with open(grid_path, "rb") as gf:
                    b64_img = base64.b64encode(gf.read()).decode()
                url = f"https://googleapis.com{CFG['GEMINI_API_KEY']}"
                body = json.dumps({"contents": [{"parts": [{"text": prompt}, {"inline_data": {"mime_type": "image/jpeg", "data": b64_img}}]}]}).encode()
                req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
                with urllib.request.urlopen(req, timeout=30) as resp:
                    ans = json.loads(resp.read().decode())["candidates"]["content"]["parts"]["text"].strip()

            clean_ans = re.sub(r'[\\/:*?"<>|]', '', ans).strip()
            if clean_ans and not any(bad in clean_ans.upper() for bad in ("UNKNOWN", "UNIDENTIFIED", "NOT SURE", "CANNOT IDENTIFY", "SORRY")):
                log(f"   -> AI Vision matched '{clean_ans}' after {total_snaps} snapshots!")
                os.remove(grid_path)
                return clean_ans
            log(f"   -> AI Vision pass {b_idx+1}/{len(batches)} ({total_snaps}/30 snapshots) inconclusive, scanning deeper...")
    except Exception as ex:
        log(f"   -> AI Vision error: {ex}")
    finally:
        if srv:
            srv.terminate()
            srv.wait(timeout=5)
    return None

def process_finished():
    fin_dir = os.path.join(MEDIA_DIR, "finished")
    hold_dir = os.path.join(MEDIA_DIR, "ai_hold")
    os.makedirs(hold_dir, exist_ok=True)
    files = [os.path.join(r, fn) for d in (fin_dir, hold_dir) for r, _, fns in os.walk(d) for fn in fns if fn.lower().endswith((".mp4", ".mkv", ".m4v")) and not fn.startswith(".")]
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
        mode = CFG.get("IDENTIFY_MODE", "db_then_ai")
        raw_title = resolve_source_title(fpath, fname)
        query = re.sub(r"(\s*\(\d{4}\)|\s*\(Unmatched\)|_SHORT_\d+m|\b(special|director.?s|extended|unrated|widescreen|fullscreen|collector.?s|anniversary|remastered|deluxe|theatrical|blu-?ray|dvd)\s*(edition|cut|version)?\b|\bt\d+\b|\b[A-Z]\d+\b)", "", clean_disc_name(raw_title), flags=re.I).strip()
        if len(query) <= 3 or query.lower() in ("unidentified", "unknown", "untitled", "disc", "dvd", "movie", "video", "main"): query = ""
        matched = query_database(query) if mode in ("db_only", "db_then_ai") and query.upper() not in ("DVD VIDEO", "DISC 1", "DISC 2", "VIDEO TS", "MOVIE") else None
        tmp_snap, has_snap = f"/tmp/grid_{int(time.time()*1000)}.jpg", False
        if not matched and mode in ("ai_only", "db_then_ai"):
            cpu_now = current_cpu_pct()
            if cpu_now >= 70.0:
                hold_dir = os.path.join(MEDIA_DIR, "ai_hold")
                os.makedirs(hold_dir, exist_ok=True)
                dest_hold = os.path.join(hold_dir, fname)
                if os.path.abspath(fpath) != os.path.abspath(dest_hold):
                    shutil.move(fpath, dest_hold)
                log(f"   -> CPU load at {cpu_now}% (>= 70%); parked in ai_hold/ until CPU is below 70%.")
                continue
            guess = identify_with_ai(fpath, info["duration_secs"], "/tmp/ai_scans")
            if os.path.exists("/tmp/ai_scans/preview_grid.jpg"):
                shutil.move("/tmp/ai_scans/preview_grid.jpg", tmp_snap)
                has_snap = True
            if guess:
                m_yr = re.search(r"\((\d{4})\)", guess)
                clean_guess = re.sub(r"\s*\(\d{4}\)", "", guess).strip()
                cand_matched = query_database(clean_guess)
                cand_year = m_yr.group(1) if m_yr else (re.search(r"\((\d{4})\)", cand_matched or "").group(1) if re.search(r"\((\d{4})\)", cand_matched or "") else None)
                actual_mins = info["duration_secs"] / 60.0
                tmdb_rt = get_tmdb_runtime(cand_matched or clean_guess, cand_year, CFG.get("TMDB_API_KEY"))
                exact_rt = (actual_mins < 45) or (tmdb_rt is not None and abs(tmdb_rt - actual_mins) <= 6.0)
                hard_mismatch = (actual_mins >= 45 and tmdb_rt is not None and abs(tmdb_rt - actual_mins) > 20.0)

                if hard_mismatch:
                    log(f"   -> FLAGGED AI hallucination: '{cand_matched or clean_guess}' (TMDB runtime {tmdb_rt}m != video {actual_mins:.0f}m); routing to (Unmatched).")
                elif exact_rt and cand_matched:
                    matched = cand_matched
                else:
                    sec_model = pick_secondary_ollama_model(CFG.get("LOCAL_AI_MODEL", "gemma3:4b")) if CFG.get("AI_PROVIDER") == "local_ollama" else None
                    if sec_model and os.path.exists(tmp_snap):
                        log(f"   -> Runtime not exact ({tmdb_rt or '?'}m vs {actual_mins:.0f}m); running second-opinion check with {sec_model}...")
                        sec_prompt = "Identify the exact movie, TV show, or concert title shown in these video frames. Reply ONLY with the clean title (and year if known). If unsure, reply UNKNOWN."
                        sec_raw = query_ollama_model(sec_model, sec_prompt, tmp_snap)
                        sec_clean = re.sub(r"\s*\(\d{4}\)", "", sec_raw).strip()
                        norm1 = re.sub(r"[^a-z0-9]", "", clean_guess.lower())
                        norm2 = re.sub(r"[^a-z0-9]", "", sec_clean.lower())
                        if norm1 and norm2 and (norm1 in norm2 or norm2 in norm1):
                            log(f"   -> Dual-model consensus confirmed '{cand_matched or clean_guess}' ({sec_model} agreed).")
                            matched = cand_matched or guess
                        else:
                            log(f"   -> FLAGGED AI disagreement: {CFG.get('LOCAL_AI_MODEL', 'gemma3:4b')}='{clean_guess}' vs {sec_model}='{sec_raw or 'UNKNOWN'}'; routing to (Unmatched).")
                    elif cand_matched:
                        matched = cand_matched
        if not matched:
            matched = f"{query or 'Unknown Disc'} (Unmatched)"
            if not has_snap and CFG.get("ENABLE_UNMATCHED_SNAPSHOTS") == "true":
                has_snap = create_snapshot_grid(fpath, tmp_snap, info["duration_secs"])
    if not matched:
        return
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
    parts = stem.split(" - ", 1)
    disc_prefix = parts[0].strip() if len(parts) == 2 else ""
    raw_stem = parts[1].strip() if len(parts) == 2 else stem
    raw_base = os.path.join(MEDIA_DIR, "raw")
    for r_root, _, r_files in os.walk(raw_base, topdown=False):
        if r_root == raw_base:
            continue
        if disc_prefix and os.path.basename(r_root) != disc_prefix:
            continue
        for cand in (f"{stem}.mkv", f"{raw_stem}.mkv"):
            if cand in r_files:
                os.remove(os.path.join(r_root, cand))
                log(f"   -> Deleted source MKV: {os.path.basename(r_root)}/{cand}")
        if not os.listdir(r_root):
            os.rmdir(r_root)
            log(f"   -> Removed empty raw folder: {os.path.basename(r_root)}/")
    if has_snap and os.path.exists(tmp_snap):
        shutil.move(tmp_snap, os.path.join(dest_dir, f"{safe}_AI_preview.jpg"))
        log(f"   -> Saved AI snapshot grid for review: {safe}_AI_preview.jpg")
    if CFG.get("SAVE_MOVIE_INFO_TXT") == "true":
        with open(os.path.join(dest_dir, f"{safe}_info.txt"), "w") as tf:
            tf.write(f"Title: {safe}\nSource: {fname}\nStatus: {'LOW QUALITY' if is_low else 'FULL QUALITY'}\nResolution: {info['width']}x{info['height']} ({info['v_codec']})\nBitrate: {info['bitrate_kbps']} kbps\nRuntime: {info['duration_mins']} mins\nAudio: {', '.join(info['a_codecs']) or 'NONE'}\n")
    log(f"   -> Routed to {base_bucket}/{safe}/")

    # Clean up any empty disc folders in raw/ (e.g. failed MakeMKV rips) older than 10 minutes
    raw_root = os.path.join(MEDIA_DIR, "raw")
    now = time.time()
    for entry in os.listdir(raw_root) if os.path.isdir(raw_root) else []:
        if entry.startswith("."):
            continue
        p = os.path.join(raw_root, entry)
        if os.path.isdir(p) and not os.listdir(p) and (now - os.path.getmtime(p)) > 600:
            try:
                os.rmdir(p)
                log(f"   -> Pruned empty raw folder: {entry}/")
            except OSError:
                pass

if __name__ == "__main__":
    os.makedirs("/tmp", exist_ok=True)
    _lock_fp = open("/tmp/organize-rips.lock", "w")
    try:
        fcntl.flock(_lock_fp, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        log("Organizer already running in another process; skipping duplicate trigger.")
        sys.exit(0)
    process_finished()
