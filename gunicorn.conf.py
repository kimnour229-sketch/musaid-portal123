# ============================================================
# Gunicorn configuration for Musaid Portal
# Run:  gunicorn -c gunicorn.conf.py app:app
# ============================================================
import multiprocessing
import os

# --- Socket ---
# Bind to a UNIX socket fronted by Nginx (preferred), or a localhost TCP port.
bind = os.environ.get("GUNICORN_BIND", "unix:/run/musaid/musaid.sock")

# --- Workers ---
# IMPORTANT: the login rate-limit / lockout state is in-memory per process.
# Keep workers = 1 unless you move that state to Redis (see SECURITY_REPORT.md).
# Once shared state exists, scale to (2 x CPU) + 1.
workers = int(os.environ.get("GUNICORN_WORKERS", "1"))
threads = int(os.environ.get("GUNICORN_THREADS", "4"))   # threads handle I/O concurrency safely
worker_class = "gthread"

# --- Timeouts (OCR / large PDF parsing can be slow) ---
timeout = int(os.environ.get("GUNICORN_TIMEOUT", "120"))
graceful_timeout = 30
keepalive = 5

# --- Limits ---
max_requests = 1000          # recycle workers to bound memory leaks
max_requests_jitter = 100
limit_request_line = 8190

# --- Logging ---
accesslog = os.environ.get("GUNICORN_ACCESS_LOG", "/var/log/musaid/access.log")
errorlog = os.environ.get("GUNICORN_ERROR_LOG", "/var/log/musaid/error.log")
loglevel = os.environ.get("GUNICORN_LOG_LEVEL", "info")

# --- Process naming ---
proc_name = "musaid"

# --- Security: respect X-Forwarded-* from the trusted Nginx proxy only ---
forwarded_allow_ips = os.environ.get("FORWARDED_ALLOW_IPS", "127.0.0.1")
