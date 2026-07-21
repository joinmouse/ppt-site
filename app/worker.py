"""Background queue worker: queued -> running -> done/failed."""
import asyncio
import json
import logging

from . import db, kimi_client

log = logging.getLogger("worker")
_stop = asyncio.Event()


async def run() -> None:
    while not _stop.is_set():
        job = db.next_queued_job()
        if job is None:
            await asyncio.sleep(2)
            continue
        db.update_job(job["id"], status="running")
        try:
            files = json.loads(job["files"] or "[]")
            result = await kimi_client.generate_ppt(
                job["description"], job["pages"] or "auto", job["style"], files)
            db.update_job(job["id"], status="done",
                          result_url=result.get("result_url"),
                          error=None if not result.get("note") else result["note"])
        except Exception as exc:  # noqa: BLE001
            log.exception("job %s failed", job["id"])
            db.update_job(job["id"], status="failed", error=str(exc)[:500])


def stop() -> None:
    _stop.set()
