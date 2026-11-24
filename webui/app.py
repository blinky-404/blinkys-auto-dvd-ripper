# ============================================================================
# Blinky's Auto DVD Ripper v2.0 - FastAPI Control Center & Telemetry Backend
# ============================================================================
import os, re, glob, json, subprocess
from datetime import datetime
from fastapi import FastAPI, Request, Query
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse, StreamingResponse, FileResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from apscheduler.schedulers.background import BackgroundScheduler

SYSTEM_DIR = os.environ.get("SYSTEM_DIR", "/DATA/ripper_system")
MEDIA_DIR = os.environ.get("MEDIA_DIR", "/DATA/ripper_media")
CONF_FILE = os.path.join(SYSTEM_DIR, "config", "organizer.conf")
LOG_DIR = os.path.join(SYSTEM_DIR, "logs")
os.makedirs(LOG_DIR, exist_ok=True)

app = FastAPI(title="Blinky's Auto DVD Ripper")
templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")
scheduler = BackgroundScheduler()

def read_conf():
    cfg = {}
    if os.path.exists(CONF_FILE):
        with open(CONF_FILE) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    cfg[k.strip()] = v.strip().strip('"').strip("'")
    return cfg

def write_conf(updates: dict):
    lines = open(CONF_FILE).readlines() if os.path.exists(CONF_FILE) else []
    seen = set()
    new_lines = []
    for line in lines:
        s = line.strip()
        if s and not s.startswith("#") and "=" in s:
            k = s.split("=", 1)[0].strip()
            if k in updates:
                val = str(updates[k])
                fmt = val if val.lower() in ("true", "false") or val.isdigit() else f'"{val}"'
                new_lines.append(f"{k}={fmt}\n")
                seen.add(k)
                continue
        new_lines.append(line)
    for k, v in updates.items():
        if k not in seen:
            fmt = str(v) if str(v).lower() in ("true", "false") or str(v).isdigit() else f'"{v}"'
            new_lines.append(f"{k}={fmt}\n")
    with open(CONF_FILE, "w") as f:
        f.writelines(new_lines)
    sync_scheduler()
    sync_scheduler()

def run_organizer_job():
    subprocess.Popen(["/app/scripts/organize-rips.sh"])

def sync_scheduler():
    cfg = read_conf()
    scheduler.remove_all_jobs()
    if cfg.get("AUTO_ORGANIZE_ENABLED", "true").lower() == "true":
        t = cfg.get("AUTO_ORGANIZE_TIME", "03:00")
        hr, mn = (t.split(":") + ["00"])[:2]
        scheduler.add_job(run_organizer_job, "cron", hour=int(hr), minute=int(mn), id="daily_org")

@app.on_event("startup")
def on_startup():
    if not scheduler.running:
        scheduler.start()
    sync_scheduler()

def detect_hardware():
    drives = []
    for sr in sorted(glob.glob("/dev/sr*")):
        name = os.path.basename(sr)
        m_path = f"/sys/block/{name}/device/model"
        model = open(m_path).read().strip() if os.path.exists(m_path) else "Optical Drive"
        drives.append({"device": sr, "model": model})
    dmesg = subprocess.run(["dmesg"], capture_output=True, text=True).stdout[-8000:] if os.path.exists("/bin/dmesg") or os.path.exists("/usr/bin/dmesg") else ""
    usb_warn = bool(re.search(r"(reset high-speed USB|error -71|error -110|over-current)", dmesg, re.I))
    gpus = ["cpu"]
    if os.path.exists("/dev/dri"):
        gpus += ["qsv", "vaapi"]
    if subprocess.run(["which", "nvidia-smi"], capture_output=True).returncode == 0:
        gpus.append("nvenc")
    return {"drives": drives, "usb_power_warning": usb_warn, "available_gpus": gpus}

@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request, "ports": {
        "makemkv": os.environ.get("MAKEMKV_PORT", "5800"),
        "handbrake": os.environ.get("HANDBRAKE_PORT", "5801"),
        "filebrowser": os.environ.get("FILEBROWSER_PORT", "8091")
    }})

import shutil
def sys_metrics():
    du = shutil.disk_usage(MEDIA_DIR)
    free_gb = round(du.free / (1024**3), 1)
    total_gb = round(du.total / (1024**3), 1)
    disk_pct = round(((du.total - du.free) / du.total) * 100, 1)
    load1 = os.getloadavg().__getitem__(0)
    cores = os.cpu_count() or 1
    cpu_pct = min(100.0, round((load1 / cores) * 100, 1))
    return {"cpu_pct": cpu_pct, "disk_pct": disk_pct, "free_gb": free_gb, "total_gb": total_gb}

def docker_sock(method, path, timeout=5):
    res = subprocess.run(["curl", "-s", "-X", method, "--unix-socket", "/var/run/docker.sock", "http://localhost" + path], capture_output=True, text=True, errors="replace", timeout=timeout)
    return res.stdout or ""

def installed_ai_models():
    m_dir = os.path.join(SYSTEM_DIR, "ollama", "models", "manifests")
    found = []
    for r, _, fs in os.walk(m_dir):
        if fs:
            found.append(os.path.basename(r))
    return sorted(set(found))

@app.get("/api/status")
# Live dashboard telemetry: optical drives, CPU load/temp, storage, and video counts
def api_status():
    hw = detect_hardware()
    counts = {k: len([f for _, _, fs in os.walk(os.path.join(MEDIA_DIR, k)) for f in fs if not f.startswith(".")])
              for k in ["raw", "finished", "organized_movies", "low_quality_quarantine", "raw_audio_backups", "short_videos", "ai_hold", "no_audio"]}
    hb_log = docker_sock("GET", "/containers/handbrake/logs?stdout=1&stderr=1&tail=30")
    if max(hb_log.rfind("Conversion ended successfully."), hb_logs.rfind("Watch folder '/watch' processing terminated.") if False else hb_log.rfind("Watch folder '/watch' processing terminated.")) > hb_log.rfind("Encoding "):
        hb_log = ""
    pct_match = re.findall(r"(\d+\.\d+)\s*%", hb_log)
    hb_progress = float(pct_match[-1]) if pct_match else 0.0
    containers = {}
    for c in ("makemkv", "handbrake", "ripper-filebrowser", "ripper-ai-vision"):
        raw = docker_sock("GET", f"/containers/{c}/json")
        fallback = "ready (0 MB idle)" if os.path.exists("/DATA/ripper_system/ollama/models/manifests") else "not_installed"
        containers[c] = json.loads(raw).get("State", {}).get("Status", fallback) if "State" in raw else fallback
    return {"hardware": hw, "counts": counts, "hb_progress": hb_progress, "sys": sys_metrics(), "ai_models": installed_ai_models(), "containers": containers}

ACTION_STATE = {"task": "System", "status": "idle", "detail": "All controls ready", "updated": ""}

@app.get("/api/action_status")
# Real-time status readout for top dashboard buttons (Restart & Run Organizer)
def api_action_status():
    return ACTION_STATE

@app.post("/api/restart/{name}")
def restart_container(name: str):
    import datetime, threading
    if name not in ("makemkv", "handbrake", "ripper-filebrowser"):
        return JSONResponse({"ok": False, "error": "Invalid container"}, status_code=400)
    def _do_restart():
        ACTION_STATE.update({"task": name, "status": "running", "detail": "Restarting container...", "updated": datetime.datetime.now().strftime("%H:%M:%S")})
        res = docker_sock("POST", f"/containers/{name}/restart", timeout=20)
        if "error" in res.lower():
            ACTION_STATE.update({"task": name, "status": "error", "detail": res[:80], "updated": datetime.datetime.now().strftime("%H:%M:%S")})
        else:
            ACTION_STATE.update({"task": name, "status": "success", "detail": "Restarted cleanly", "updated": datetime.datetime.now().strftime("%H:%M:%S")})
    threading.Thread(target=_do_restart, daemon=True).start()
    return {"ok": True}

@app.post("/api/organize")
def trigger_organize():
    import datetime, threading
    def _do_org():
        ACTION_STATE.update({"task": "Organizer", "status": "running", "detail": "Inspecting & identifying files (AI Vision may take ~25s)...", "updated": datetime.datetime.now().strftime("%H:%M:%S")})
        try:
            r = subprocess.run(["/app/scripts/organize-rips.sh"], capture_output=True, text=True)
            if r.returncode != 0:
                raise RuntimeError((r.stderr or r.stdout or "Exit " + str(r.returncode)).strip().splitlines()[-1])
            ACTION_STATE.update({"task": "Organizer", "status": "success", "detail": "Completed cleanly", "updated": datetime.datetime.now().strftime("%H:%M:%S")})
        except Exception as ex:
            ACTION_STATE.update({"task": "Organizer", "status": "error", "detail": str(ex)[:80], "updated": datetime.datetime.now().strftime("%H:%M:%S")})
    threading.Thread(target=_do_org, daemon=True).start()
    return {"ok": True}

@app.get("/api/config")
def get_config():
    cfg = read_conf()
    for secret_k in ("TMDB_API_KEY", "AI_API_KEY"):
        if cfg.get(secret_k):
            cfg[secret_k] = "********"
    return cfg

@app.post("/api/config")
async def save_config(request: Request):
    data = await request.json()
    write_conf(data)
    cpu_pct = int(data.get("MAX_CPU_PERCENT", 100))
    if 10 <= cpu_pct < 100:
        cpus = round((os.cpu_count() or 2) * (cpu_pct / 100.0), 2)
        subprocess.run(["docker", "update", f"--cpus={cpus}", "handbrake", "makemkv"], capture_output=True)
    return {"ok": True}
    return {"ok": True}

@app.post("/api/ai/install")
async def install_local_ai(request: Request):
    model = (await request.json()).get("model", "gemma3:4b")
    cmd = f"docker rm -f ripper-ai-vision >/dev/null 2>&1; docker run -d --name ripper-ai-vision -p 127.0.0.1:11434:11434 -v {SYSTEM_DIR}/ollama:/root/.ollama ollama/ollama:latest && sleep 3 && docker exec ripper-ai-vision ollama pull {model} && docker stop ripper-ai-vision"
    subprocess.Popen(["bash", "-c", cmd])
    return {"ok": True, "message": f"Pulling {model} in background; container will stop automatically once ready."}

def format_eject_banners(lines):
    out, last_ok = [], True
    for l in lines:
        if "Disc rip terminated successfully" in l: last_ok = True
        elif "Disc rip terminated with failure" in l: last_ok = False
        if "Ejecting disc from" in l:
            tag = "[EJECTED - SUCCESS]" if last_ok else "[EJECTED - FAILED]"
            out.append(f"=== {tag} {l.split(']')[-1].strip()} ===")
        else:
            out.append(l)
    return out

def clean_progress_spam(lines):
    is_prog = lambda l: ("Current progress -" in l) or ("Encoding " in l and "task " in l) or ("fps, avg " in l and "ETA " in l)
    kept = [l for l in lines if not is_prog(l)]
    prog = [l for l in lines if is_prog(l)]
    if prog:
        kept.append("--- Latest Progress: " + " ".join(p.strip() for p in prog[-2:]) + " ---")
    return kept[-80:]

def collect_logs():
    mk_raw = docker_sock("GET", "/containers/makemkv/logs?stdout=1&stderr=1&tail=1000")
    mk_filt = "\n".join(clean_progress_spam(format_eject_banners([l for l in mk_raw.splitlines() if re.search(r"(error|fail|sector|hash|title|cell|skip|eject|complete|rip|autodiscripper|disc|backing|detect|finish|saved|start|operation)", l, re.I)])))
    hb_raw = docker_sock("GET", "/containers/handbrake/logs?stdout=1&stderr=1&tail=150")
    hb_filt = "\n".join(clean_progress_spam([l for l in hb_raw.splitlines() if re.search(r"(error|fail|encoding|complete|scan|title|fps, avg)", l, re.I)]))
    aud = open(os.path.join(LOG_DIR, "audio_audit.log")).read() if os.path.exists(os.path.join(LOG_DIR, "audio_audit.log")) else ""
    org = open(os.path.join(LOG_DIR, "organizer.log")).read() if os.path.exists(os.path.join(LOG_DIR, "organizer.log")) else ""
    return {"makemkv": mk_filt or "No MakeMKV warnings logged.", "handbrake": hb_filt or "No HandBrake warnings logged.", "audio": aud or "No audio audit entries yet.", "organizer": org or "No organizer logs yet."}

@app.get("/api/logs")
def get_logs():
    return collect_logs()

@app.get("/api/logs/export")
def export_logs(sections: str = "makemkv,audio,handbrake,organizer", save_server: bool = False):
    data = collect_logs()
    chosen = [s.strip() for s in sections.split(",") if s.strip() in data]
    report = f"=== Blinky's Auto DVD Ripper Diagnostic Report ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')}) ===\n\n"
    for s in chosen:
        report += f"--- [{s.upper()}] ---\n{data[s]}\n\n"
    if save_server:
        out = os.path.join(MEDIA_DIR, "organized_movies", f"ripper_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt")
        open(out, "w").write(report)
    return PlainTextResponse(report, headers={"Content-Disposition": "attachment; filename=ripper_report.txt"})

@app.get("/api/media/list")
def list_media():
    items = []
    for folder in ["raw", "finished", "organized_movies", "low_quality_quarantine", "raw_audio_backups", "short_videos", "ai_hold", "no_audio"]:
        base = os.path.join(MEDIA_DIR, folder)
        for r, _, fns in os.walk(base):
            for fn in sorted(fns):
                if fn.lower().endswith((".mp4", ".mkv", ".m4v")):
                    full = os.path.join(r, fn)
                    items.append({"folder": folder, "rel": os.path.relpath(full, MEDIA_DIR), "name": fn, "mb": round(os.path.getsize(full) / (1024*1024), 1)})
    return items

@app.get("/api/media/stream")
def stream_media(path: str = Query(...)):
    full = os.path.abspath(os.path.join(MEDIA_DIR, path))
    if not full.startswith(os.path.abspath(MEDIA_DIR)) or not os.path.exists(full):
        return JSONResponse({"error": "Not found"}, status_code=404)
    if full.lower().endswith(".mp4"):
        return FileResponse(full, media_type="video/mp4")
    proc = subprocess.Popen(["ffmpeg", "-hide_banner", "-loglevel", "error", "-i", full, "-c:v", "libx264", "-preset", "ultrafast", "-crf", "26", "-c:a", "aac", "-b:a", "128k", "-movflags", "frag_keyframe+empty_moov", "-f", "mp4", "pipe:1"], stdout=subprocess.PIPE)
    return StreamingResponse(iter(lambda: proc.stdout.read(65536), b""), media_type="video/mp4")
    items = []
    for folder in ["raw", "finished", "organized_movies", "low_quality_quarantine", "raw_audio_backups", "short_videos", "ai_hold", "no_audio"]:
        base = os.path.join(MEDIA_DIR, folder)
        for r, _, fns in os.walk(base):
            for fn in sorted(fns):
                if fn.lower().endswith((".mp4", ".mkv", ".m4v")):
                    full = os.path.join(r, fn)
                    items.append({"folder": folder, "rel": os.path.relpath(full, MEDIA_DIR), "name": fn, "mb": round(os.path.getsize(full) / (1024*1024), 1)})
    return items

@app.get("/api/media/stream")
def stream_media(path: str = Query(...)):
    full = os.path.abspath(os.path.join(MEDIA_DIR, path))
    if not full.startswith(os.path.abspath(MEDIA_DIR)) or not os.path.exists(full):
        return JSONResponse({"error": "Not found"}, status_code=404)
    if full.lower().endswith(".mp4"):
        return FileResponse(full, media_type="video/mp4")
    proc = subprocess.Popen(["ffmpeg", "-hide_banner", "-loglevel", "error", "-i", full, "-c:v", "libx264", "-preset", "ultrafast", "-crf", "26", "-c:a", "aac", "-b:a", "128k", "-movflags", "frag_keyframe+empty_moov", "-f", "mp4", "pipe:1"], stdout=subprocess.PIPE)
    return StreamingResponse(iter(lambda: proc.stdout.read(65536), b""), media_type="video/mp4")


@app.get("/api/check-update")
def check_update():
    if not os.path.isdir("/repo/.git"):
        return {"ok": False, "error": "Repo mount /repo not found"}
    try:
        subprocess.run(["git", "-C", "/repo", "config", "--global", "--add", "safe.directory", "/repo"], check=False)
        subprocess.run(["git", "-C", "/repo", "fetch", "origin", "main"], check=True, timeout=20, capture_output=True)
        local_sha = subprocess.check_output(["git", "-C", "/repo", "rev-parse", "--short", "HEAD"], text=True).strip()
        remote_sha = subprocess.check_output(["git", "-C", "/repo", "rev-parse", "--short", "origin/main"], text=True).strip()
        msg = subprocess.check_output(["git", "-C", "/repo", "log", "-1", "--pretty=%s", "origin/main"], text=True).strip()
        return {"ok": True, "up_to_date": local_sha == remote_sha, "local": local_sha, "remote": remote_sha, "latest_msg": msg}
    except Exception as e:
        return {"ok": False, "error": str(e)}

@app.post("/api/update-stack")
def update_stack():
    if not os.path.isdir("/repo/.git"):
        return JSONResponse({"ok": False, "error": "Repo mount /repo not found"}, status_code=400)
    try:
        subprocess.run(["git", "-C", "/repo", "config", "--global", "--add", "safe.directory", "/repo"], check=False)
        subprocess.run(["git", "-C", "/repo", "pull", "origin", "main"], check=True, timeout=30, capture_output=True)
        os.makedirs(os.path.join(MEDIA_DIR, "ai_hold"), exist_ok=True)
        hook_src = "/repo/scripts/handbrake-post-conversion.sh"
        hook_dst = os.path.join(SYSTEM_DIR, "handbrake", "hooks", "post_conversion.sh")
        if os.path.exists(hook_src):
            os.makedirs(os.path.dirname(hook_dst), exist_ok=True)
            shutil.copyfile(hook_src, hook_dst)
            os.chmod(hook_dst, 0o755)
        # Launch detached rebuild using host docker CLI if present, or restart ripper-ui via docker socket
        subprocess.Popen(["sh", "-c", "sleep 1 && docker compose -f /repo/docker-compose.yml up -d --build || true"], start_new_session=True)
        return {"ok": True, "message": "Update pulled! Rebuilding container — page will reload in 25 seconds..."}
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)
