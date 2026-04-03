import subprocess
import sys
import os

def handler(request):
    return {"statusCode": 200, "body": "FastAPI app is running."}

if __name__ == "__main__":
    os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    subprocess.run([
        sys.executable, "-m", "uvicorn", "backend:app",
        "--host", "0.0.0.0",
        "--port", "8000",
    ])
