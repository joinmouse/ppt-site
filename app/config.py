"""Environment configuration. Secrets live here only, never in frontend HTML."""
import os

ADMIN_TOKEN = os.environ.get("ADMIN_TOKEN", "")
KIMI_WEB_KEY = os.environ.get("KIMI_WEB_KEY", "")
DATA_DIR = os.environ.get("DATA_DIR", "data")
DB_PATH = os.environ.get("DB_PATH", os.path.join(DATA_DIR, "ppt-site.db"))
