"""FastAPI entry: pages, public API, admin API."""
import json
import os
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

import asyncio
from fastapi import FastAPI, File, Form, Header, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from . import config, db, worker

STATIC = Path(__file__).parent / "static"
MAX_FILES = 50
MAX_FILE_SIZE = 100 * 1024 * 1024


@asynccontextmanager
async def lifespan(app: FastAPI):
    os.makedirs(config.DATA_DIR, exist_ok=True)
    db.init_db()
    task = asyncio.create_task(worker.run())
    yield
    worker.stop()
    task.cancel()


app = FastAPI(title="ppt-site", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=STATIC), name="static")


# ---------- pages ----------
@app.get("/submit")
def page_submit():
    return FileResponse(STATIC / "submit.html")


@app.get("/status/{job_id}")
def page_status(job_id: str):
    return FileResponse(STATIC / "status.html")


@app.get("/admin")
def page_admin():
    return FileResponse(STATIC / "admin.html")


@app.get("/")
def page_root():
    return FileResponse(STATIC / "submit.html")


# ---------- public api ----------
@app.get("/api/hashes/{h}/check")
def api_check_hash(h: str):
    return db.check_hash(h)


@app.post("/api/jobs")
async def api_create_job(
    hash: str = Form(...),
    description: str = Form(...),
    pages: str = Form("auto"),
    style: str = Form(...),
    files: list[UploadFile] = File(default=[]),
):
    if not description.strip():
        raise HTTPException(400, "description required")
    if style not in ("classic", "smart"):
        raise HTTPException(400, "invalid style")
    if len(files) > MAX_FILES:
        raise HTTPException(400, f"too many files (max {MAX_FILES})")

    job_id = uuid.uuid4().hex
    # Atomic one-time consumption — the core invariant of this site.
    if not db.consume_hash(hash, job_id):
        raise HTTPException(409, "link invalid or already used")

    saved: list[str] = []
    upload_dir = os.path.join(config.DATA_DIR, "uploads", job_id)
    os.makedirs(upload_dir, exist_ok=True)
    try:
        for f in files:
            data = await f.read()
            if len(data) > MAX_FILE_SIZE:
                raise HTTPException(400, f"file too large: {f.filename}")
            safe = os.path.basename(f.filename or "file")
            with open(os.path.join(upload_dir, safe), "wb") as out:
                out.write(data)
            saved.append(safe)
    except HTTPException:
        raise

    db.create_job(job_id, hash, description.strip(), pages, style, json.dumps(saved))
    return {"job_id": job_id}


@app.get("/api/jobs/{job_id}")
def api_get_job(job_id: str):
    job = db.get_job(job_id)
    if not job:
        raise HTTPException(404, "job not found")
    return {
        "id": job["id"],
        "status": job["status"],
        "position": db.queue_position(job_id),
        "description": job["description"],
        "pages": job["pages"],
        "style": job["style"],
        "result_url": job["result_url"],
        "error": job["error"],
        "created_at": job["created_at"],
        "updated_at": job["updated_at"],
    }


# ---------- admin api ----------
def _auth(x_admin_token: str | None) -> None:
    if not config.ADMIN_TOKEN:
        raise HTTPException(503, "ADMIN_TOKEN not configured")
    if x_admin_token != config.ADMIN_TOKEN:
        raise HTTPException(401, "invalid admin token")


@app.post("/api/admin/hashes")
def api_admin_create(count: int = Form(...), note: str = Form(""),
                     x_admin_token: str | None = Header(None)):
    _auth(x_admin_token)
    if not 1 <= count <= 500:
        raise HTTPException(400, "count must be 1..500")
    return {"hashes": db.create_hashes(count, note)}


@app.get("/api/admin/hashes")
def api_admin_list(filter: str = "all", x_admin_token: str | None = Header(None)):
    _auth(x_admin_token)
    return db.list_hashes(filter)


@app.exception_handler(HTTPException)
def http_exc_handler(request, exc):
    return JSONResponse({"error": exc.detail}, status_code=exc.status_code)
