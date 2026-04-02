import base64
import json

import requests
from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from db import get_db, Webhook
from fastapi.middleware.cors import CORSMiddleware
 
app = FastAPI()
 
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

USERS_FILE = "users.json"
GITHUB_CONFIG_REPO    = "shashanktu/repo_onboard_full"
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

class NewWebhookRequest(BaseModel):
    github_username: str
    repo_name: str
    pat: str
    prev_webhook_url: str
    curr_webhook_url: str

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
def get_webhook_url(db: Session = Depends(get_db)):
    webhook = db.query(Webhook).first()
    if not webhook:
        raise HTTPException(status_code=404, detail="No webhook config found in database.")
    return {"CURR_WEBHOOK_URL": webhook.curr_webhook_url, "PREV_WEBHOOK_URL": webhook.prev_webhook_url}


@app.post("/config/webhook-url")
def update_webhook_url_config(req: UpdateConfigRequest, db: Session = Depends(get_db)):
    webhook = db.query(Webhook).first()
    if not webhook:
        webhook = Webhook(curr_webhook_url=req.new_url, prev_webhook_url=None)
        db.add(webhook)
    else:
        webhook.prev_webhook_url = webhook.curr_webhook_url
        webhook.curr_webhook_url = req.new_url
    db.commit()
    return {"success": True}


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

@app.post("/webhook/update")
def update_webhook(req: NewWebhookRequest):

    print("Previous url:", req.prev_webhook_url,"Current url:", req.curr_webhook_url)
    url = f"https://api.github.com/repos/{req.github_username}/{req.repo_name}/hooks"
    headers = {"Authorization": f"token {req.pat}", "Accept": "application/vnd.github+json"}
    resp = requests.get(url, headers=headers)
    if resp.status_code != 200:
        raise HTTPException(status_code=resp.status_code, detail="Failed to fetch webhooks.")
    hook_id = None
    for hook in resp.json():
        if hook.get("config", {}).get("url") == req.prev_webhook_url:
            hook_id = hook["id"]
    if not hook_id:
        payload = {
            "name": "web", "active": True,
            "events": ["push", "pull_request"],
            "config": {"url": req.curr_webhook_url, "content_type": "application/json", "insecure_ssl": "0"},
        }
        resp = requests.post(url, headers=headers, json=payload)
    else:
        url = f"https://api.github.com/repos/{req.github_username}/{req.repo_name}/hooks/{hook_id}"
        payload = {"config": {"url": req.curr_webhook_url, "content_type": "application/json", "insecure_ssl": "0"}}
        resp = requests.patch(url, headers=headers, json=payload)
    return {"status_code": resp.status_code, "body": resp.json()}
