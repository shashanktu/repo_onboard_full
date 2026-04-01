import subprocess
import sys
import threading
import os

_started = False

def start_streamlit():
    global _started
    if not _started:
        _started = True
        subprocess.Popen([
            sys.executable, "-m", "streamlit", "run", "app.py",
            "--server.port", "8501",
            "--server.headless", "true",
            "--server.enableCORS", "false",
            "--server.enableXsrfProtection", "false",
        ])

threading.Thread(target=start_streamlit, daemon=True).start()

def app(environ, start_response):
    import urllib.request
    try:
        resp = urllib.request.urlopen("http://localhost:8501" + (environ.get("PATH_INFO") or "/"))
        body = resp.read()
        status = f"{resp.status} OK"
        headers = [(k, v) for k, v in resp.headers.items()]
    except Exception as e:
        body = b"Starting up, please refresh..."
        status = "200 OK"
        headers = [("Content-Type", "text/plain")]

    start_response(status, headers)
    return [body]
