import base64
import json

import requests
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI()

USERS_FILE = "users.json"
GITHUB_CONFIG_REPO    = "shashanktu/Repo_Onboarding"
GITHUB_CONFIG_PATH    = "config.json"
GITHUB_CONFIG_RAW_URL = f"https://raw.githubusercontent.com/{GITHUB_CONFIG_REPO}/main/{GITHUB_CONFIG_PATH}"
GITHUB_CONFIG_API_URL = f"https://api.github.com/repos/{GITHUB_CONFIG_REPO}/contents/{GITHUB_CONFIG_PATH}"


# ── Pydantic models ───────────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    username: str
    password: str

class WebhookRequest(BaseModel):
    github_username: str
    repo_name: str
    pat: str
    webhook_url: str

class PatchWebhookRequest(BaseModel):
    github_username: str
    repo_name: str
    pat: str
    hook_id: int
    new_url: str

class UpdateConfigRequest(BaseModel):
    new_url: str
    pat: str


# ── Auth ──────────────────────────────────────────────────────────────────────

@app.post("/auth/login")
def login(req: LoginRequest):
    with open(USERS_FILE, "r") as f:
        users = json.load(f)
    for user in users:
        if user["username"] == req.username and user["password"] == req.password:
            return {"success": True, "user": user}
    return {"success": False}


# ── GitHub config ─────────────────────────────────────────────────────────────

@app.get("/config/webhook-url")
def get_webhook_url():
    resp = requests.get(GITHUB_CONFIG_RAW_URL)
    if resp.status_code == 200:
        return resp.json()
    raise HTTPException(status_code=502, detail="Failed to fetch remote config.")


@app.post("/config/webhook-url")
def update_webhook_url_config(req: UpdateConfigRequest):
    headers = {"Authorization": f"token {req.pat}", "Accept": "application/vnd.github+json"}
    meta = requests.get(GITHUB_CONFIG_API_URL, headers=headers)
    if meta.status_code != 200:
        raise HTTPException(status_code=meta.status_code, detail=f"Could not fetch config metadata. Status: {meta.status_code}")
    sha = meta.json()["sha"]
    resp_raw = requests.get(GITHUB_CONFIG_RAW_URL)
    current_config = resp_raw.json() if resp_raw.status_code == 200 else {}
    current_config["CURR_WEBHOOK_URL"] = req.new_url
    content = base64.b64encode(json.dumps(current_config, indent=4).encode()).decode()
    payload = {"message": f"Update CURR_WEBHOOK_URL to {req.new_url}", "content": content, "sha": sha}
    resp = requests.put(GITHUB_CONFIG_API_URL, headers=headers, json=payload)
    if resp.status_code in (200, 201):
        return {"success": True}
    raise HTTPException(status_code=resp.status_code, detail=resp.json().get("message", "Unknown error"))


# ── Repos ─────────────────────────────────────────────────────────────────────

@app.get("/repos")
def get_repos(pat: str):
    headers = {"Authorization": f"token {pat}"}
    resp = requests.get(
        "https://api.github.com/user/repos?per_page=100&sort=updated&affiliation=owner",
        headers=headers,
    )
    if resp.status_code == 200:
        return {"repos": resp.json()}
    raise HTTPException(status_code=resp.status_code, detail=f"Failed to fetch repos. Status: {resp.status_code}")


# ── Webhooks ──────────────────────────────────────────────────────────────────

@app.post("/webhook/exists")
def check_webhook_exists(req: WebhookRequest):
    url = f"https://api.github.com/repos/{req.github_username}/{req.repo_name}/hooks"
    headers = {"Authorization": f"token {req.pat}", "Accept": "application/vnd.github+json"}
    resp = requests.get(url, headers=headers)
    if resp.status_code == 200:
        exists = any(h.get("config", {}).get("url") == req.webhook_url for h in resp.json())
        return {"exists": exists}
    raise HTTPException(status_code=resp.status_code, detail="Failed to fetch webhooks.")


@app.post("/webhook/create")
def create_webhook(req: WebhookRequest):
    url = f"https://api.github.com/repos/{req.github_username}/{req.repo_name}/hooks"
    headers = {"Authorization": f"token {req.pat}", "Accept": "application/vnd.github+json"}
    payload = {
        "name": "web", "active": True,
        "events": ["push", "pull_request"],
        "config": {"url": req.webhook_url, "content_type": "application/json", "insecure_ssl": "0"},
    }
    resp = requests.post(url, headers=headers, json=payload)
    return {"status_code": resp.status_code, "body": resp.json()}


@app.post("/webhook/hook-id")
def get_webhook_id(req: WebhookRequest):
    url = f"https://api.github.com/repos/{req.github_username}/{req.repo_name}/hooks"
    headers = {"Authorization": f"token {req.pat}", "Accept": "application/vnd.github+json"}
    resp = requests.get(url, headers=headers)
    if resp.status_code == 200:
        for hook in resp.json():
            if hook.get("config", {}).get("url") == req.webhook_url:
                return {"hook_id": hook["id"]}
        return {"hook_id": None}
    raise HTTPException(status_code=resp.status_code, detail="Failed to fetch webhooks.")


@app.post("/webhook/patch")
def patch_webhook(req: PatchWebhookRequest):
    url = f"https://api.github.com/repos/{req.github_username}/{req.repo_name}/hooks/{req.hook_id}"
    headers = {"Authorization": f"token {req.pat}", "Accept": "application/vnd.github+json"}
    payload = {"config": {"url": req.new_url, "content_type": "application/json", "insecure_ssl": "0"}}
    resp = requests.patch(url, headers=headers, json=payload)
    return {"status_code": resp.status_code, "body": resp.json()}
