import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["DATA_DIR"] = "/tmp/pptsite-test"
os.environ["DB_PATH"] = "/tmp/pptsite-test/test.db"
os.environ["ADMIN_TOKEN"] = "test-token"
os.environ["KIMI_WEB_KEY"] = ""  # mock mode
os.environ["MOCK_GEN_SECONDS"] = "0.2"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402


@pytest.fixture(scope="module")
def client():
    import shutil
    shutil.rmtree("/tmp/pptsite-test", ignore_errors=True)
    with TestClient(app) as c:
        yield c


def _mk_hash(client, n=1):
    r = client.post("/api/admin/hashes", data={"count": n},
                    headers={"X-Admin-Token": "test-token"})
    assert r.status_code == 200
    return r.json()["hashes"]


def test_admin_auth_required(client):
    assert client.get("/api/admin/hashes").status_code == 401
    assert client.post("/api/admin/hashes", data={"count": 1}).status_code == 401


def test_hash_lifecycle(client):
    h = _mk_hash(client)[0]
    assert client.get(f"/api/hashes/{h}/check").json() == {"valid": True}
    # consume
    r = client.post("/api/jobs", data={
        "hash": h, "description": "年终总结 PPT", "pages": "6-10", "style": "classic"})
    assert r.status_code == 200
    job_id = r.json()["job_id"]
    # second submit with same hash -> 409
    r2 = client.post("/api/jobs", data={
        "hash": h, "description": "again", "pages": "auto", "style": "smart"})
    assert r2.status_code == 409
    # check now reports used
    chk = client.get(f"/api/hashes/{h}/check").json()
    assert chk == {"valid": False, "reason": "used"}
    # job visible
    j = client.get(f"/api/jobs/{job_id}").json()
    assert j["status"] in ("queued", "running", "done")
    assert j["description"] == "年终总结 PPT"


def test_unknown_hash_409(client):
    r = client.post("/api/jobs", data={
        "hash": "nope", "description": "x", "pages": "auto", "style": "smart"})
    assert r.status_code == 409


def test_style_validation(client):
    h = _mk_hash(client)[0]
    r = client.post("/api/jobs", data={
        "hash": h, "description": "x", "pages": "auto", "style": "bogus"})
    assert r.status_code == 400


def test_pages_served(client):
    assert client.get("/submit").status_code == 200
    assert client.get("/admin").status_code == 200
    assert client.get("/status/abc").status_code == 200


def test_admin_stats(client):
    _mk_hash(client, 3)
    r = client.get("/api/admin/hashes", headers={"X-Admin-Token": "test-token"})
    stats = r.json()["stats"]
    assert stats["total"] >= 4 and stats["used"] >= 1


def test_mock_worker_completes(client):
    import time
    h = _mk_hash(client)[0]
    r = client.post("/api/jobs", data={
        "hash": h, "description": "等待 worker", "pages": "1-5", "style": "smart"})
    job_id = r.json()["job_id"]
    deadline = time.time() + 25
    status = "queued"
    while time.time() < deadline:
        status = client.get(f"/api/jobs/{job_id}").json()["status"]
        if status in ("done", "failed"):
            break
        time.sleep(1)
    assert status == "done"
