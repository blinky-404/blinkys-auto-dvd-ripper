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
    return {"drives": drives, "usb_power_warning": usb_warn, "available_gpus": gpus,
        "ram_gb": round(sum(int(l.split().pop(1)) for l in open("/proc/meminfo") if l.startswith("MemTotal:")) / (1024 * 1024), 1),
        "cpu_cores": os.cpu_count() or 1}

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

def docker_sock(method, path, timeout=5, body=None):
    cmd = ["curl", "-s", "-X", method, "--unix-socket", "/var/run/docker.sock"]
    if body is not None:
        cmd += ["-H", "Content-Type: application/json", "-d", body]
    cmd.append("http://localhost" + path)
    res = subprocess.run(cmd, capture_output=True, text=True, errors="replace", timeout=timeout)
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
async def ai_install(request: Request):
    data = await request.json()
    m1 = (data.get("model") or "gemma3:4b").strip()
    m2 = (data.get("secondary_model") or "").strip()
    models = list(dict.fromkeys([m for m in [m1, m2] if m and m.lower() != "none"]))
    state_file = os.path.join(SYSTEM_DIR, "logs", "ai_install.json")
    os.makedirs(os.path.dirname(state_file), exist_ok=True)

    def _run_pull():
        def save(active, pct, text):
            with open(state_file, "w") as f:
                json.dump({"active": active, "pct": pct, "text": text}, f)
        try:
            save(True, 1, f"Preparing Ollama container for {', '.join(models)}...")
            docker_sock("DELETE", "/containers/ripper-ai-vision?force=true")
            create_body = json.dumps({
                "Image": "ollama/ollama:latest",
                "HostConfig": {
                    "Binds": ["/DATA/ripper_system/ollama:/root/.ollama"],
                    "PortBindings": {"11434/tcp": [{"HostIp": "127.0.0.1", "HostPort": "11434"}]}
                }
            })
            res = docker_sock("POST", "/containers/create?name=ripper-ai-vision", create_body)
            if "No such image" in res:
                save(True, 1, "Pulling ollama/ollama:latest engine image (first-time setup)...")
                docker_sock("POST", "/images/create?fromImage=ollama/ollama&tag=latest")
                res = docker_sock("POST", "/containers/create?name=ripper-ai-vision", create_body)
            docker_sock("POST", "/containers/ripper-ai-vision/start")

            tags_url = "http://127.0.0.1" + ":11434/api/tags"
            pull_url = "http://127.0.0.1" + ":11434/api/pull"
            for _ in range(30):
                try:
                    urllib.request.urlopen(tags_url, timeout=1)
                    break
                except Exception:
                    time.sleep(1)

            for idx, m in enumerate(models):
                save(True, int((idx / len(models)) * 100), f"Pulling {m} ({idx+1}/{len(models)})...")
                req = urllib.request.Request(pull_url, data=json.dumps({"name": m, "stream": True}).encode(), headers={"Content-Type": "application/json"})
                t0, start_bytes = time.time(), None
                with urllib.request.urlopen(req, timeout=3600) as resp:
                    for raw in resp:
                        if not raw.strip():
                            continue
                        ev = json.loads(raw.decode("utf-8", errors="ignore"))
                        if ev.get("error"):
                            raise RuntimeError(ev["error"])
                        tot, comp = ev.get("total") or 0, ev.get("completed") or 0
                        status = ev.get("status", "downloading")
                        if tot > 0:
                            if start_bytes is None:
                                start_bytes, t0 = comp, time.time()
                            frac = min(1.0, comp / tot)
                            overall = int(((idx + frac) / len(models)) * 100)
                            elapsed = max(0.5, time.time() - t0)
                            spd = max(0.0, (comp - start_bytes) / elapsed)
                            eta_s = int((tot - comp) / spd) if spd > 1024 else 0
                            eta_str = f" • ETA {eta_s // 60}m {eta_s % 60:02d}s" if eta_s > 0 else ""
                            spd_mb = spd / (1024 * 1024)
                            save(True, overall, f"Pulling {m} ({idx+1}/{len(models)}): {int(frac*100)}% ({comp/1e9:.2f} / {tot/1e9:.2f} GB • {spd_mb:.1f} MB/s{eta_str})")
                        else:
                            save(True, int((idx / len(models)) * 100), f"{m} ({idx+1}/{len(models)}): {status}")
            save(False, 100, f"Installed: {', '.join(models)} (0 Idle RAM — container stopped)")
        except Exception as ex:
            save(False, 0, f"Error installing models: {ex}")
        finally:
            docker_sock("POST", "/containers/ripper-ai-vision/stop")

    threading.Thread(target=_run_pull, daemon=True).start()
    return {"ok": True, "message": f"Starting download for {', '.join(models)}..."}

@app.get("/api/ai/install-status")
def ai_install_status():
    state_file = os.path.join(SYSTEM_DIR, "logs", "ai_install.json")
    if not os.path.exists(state_file):
        return {"active": False, "pct": 0, "text": ""}
    try:
        return json.load(open(state_file))
    except Exception:
        return {"active": False, "pct": 0, "text": ""}

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

@app.get("/api/update-log")
def get_update_log():
    log_path = os.path.join(SYSTEM_DIR, "logs", "update.log")
    if not os.path.exists(log_path):
        return {"log": ""}
    with open(log_path, "r", errors="replace") as f:
        return {"log": f.read()[-8000:]}

@app.post("/api/update-stack")
def update_stack():
    if not os.path.isdir("/repo/.git"):
        return JSONResponse({"ok": False, "error": "Repo mount /repo not found"}, status_code=400)
    log_path = os.path.join(SYSTEM_DIR, "logs", "update.log")
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    try:
        with open(log_path, "w") as lf:
            lf.write("=== Starting Stack Update ===\n[1/4] Pulling latest commits from origin/main...\n")
        subprocess.run(["git", "-C", "/repo", "config", "--global", "--add", "safe.directory", "/repo"], check=False)
        st = os.stat("/repo")
        pull = subprocess.run(["git", "-C", "/repo", "pull", "origin", "main"], check=True, timeout=30, capture_output=True, text=True)
        subprocess.run(["chown", "-R", f"{st.st_uid}:{st.st_gid}", "/repo"], check=False)
        with open(log_path, "a") as lf:
            lf.write(pull.stdout + pull.stderr + "\n[2/4] Updating ai_hold folder & HandBrake post_conversion.sh hook...\n")
        os.makedirs(os.path.join(MEDIA_DIR, "ai_hold"), exist_ok=True)
        hook_src = "/repo/scripts/handbrake-post-conversion.sh"
        hook_dst = os.path.join(SYSTEM_DIR, "handbrake", "hooks", "post_conversion.sh")
        if os.path.exists(hook_src):
            os.makedirs(os.path.dirname(hook_dst), exist_ok=True)
            shutil.copyfile(hook_src, hook_dst)
            os.chmod(hook_dst, 0o755)
        # Inspect ripper-ui via Docker Unix socket to find the exact host path for /repo
        info = json.loads(docker_sock("GET", "/containers/ripper-ui/json"))
        host_repo = next((m["Source"] for m in info.get("Mounts", []) if m.get("Destination") == "/repo"), "")
        proj_name = info.get("Config", {}).get("Labels", {}).get("com.docker.compose.project", "blinkys-auto-dvd-ripper")
        with open(log_path, "a") as lf:
            lf.write(f"[3/4] Launching detached Docker Compose rebuild from {host_repo}...\n")
        docker_sock("DELETE", "/containers/ripper-updater?force=1")
        if "No such image" in docker_sock("GET", "/images/docker:cli/json"):
            subprocess.run(["curl", "-s", "-X", "POST", "--unix-socket", "/var/run/docker.sock", "http://localhost/images/create?fromImage=docker&tag=cli"], check=True, timeout=180, capture_output=True)
        create_payload = json.dumps({
            "Image": "docker:cli",
            "WorkingDir": "/repo",
            "Cmd": ["sh", "-c", f"docker compose -p {proj_name} up -d --build >> /logs/update.log 2>&1 && echo '[4/4] === UPDATE COMPLETE ===' >> /logs/update.log || echo '[ERROR] Rebuild failed' >> /logs/update.log"],
            "HostConfig": {
                "AutoRemove": True,
                "Binds": [
                    "/var/run/docker.sock:/var/run/docker.sock",
                    f"{host_repo}:/repo",
                    f"{SYSTEM_DIR}/logs:/logs"
                ]
            }
        })
        created = json.loads(docker_sock("POST", "/containers/create?name=ripper-updater", timeout=15, body=create_payload))
        cid = created.get("Id")
        if not cid:
            raise RuntimeError(f"Failed to create updater container: {created}")
        docker_sock("POST", f"/containers/{cid}/start")
        return {"ok": True, "message": "Rebuilding containers in background..."}
    except Exception as e:
        with open(log_path, "a") as lf:
            lf.write(f"[ERROR] {e}\n")
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


import time
def _finished_watcher_loop():
    trig = os.path.join(MEDIA_DIR, "finished", ".trigger_organizer")
    while True:
        try:
            time.sleep(2)
            if os.path.exists(trig):
                try:
                    os.remove(trig)
                except OSError:
                    pass
                subprocess.run(["python3", "/app/scripts/organize-rips.py"], check=False)
        except Exception as e:
            print(f"[WATCHER ERROR] {e}", flush=True)
            time.sleep(5)

import threading
threading.Thread(target=_finished_watcher_loop, daemon=True).start()
