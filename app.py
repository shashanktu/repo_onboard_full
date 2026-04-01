import base64
import json
import requests
import streamlit as st

st.set_page_config(page_title="GitHub Repo Onboarding", layout="wide", page_icon="ValueMomentum_logo.png")

REPOS_PER_PAGE = 10
USERS_FILE = "users.json"
GITHUB_CONFIG_REPO    = "shashanktu/repo_onboard_full"
GITHUB_CONFIG_PATH    = "config.json"
GITHUB_CONFIG_RAW_URL = f"https://raw.githubusercontent.com/{GITHUB_CONFIG_REPO}/main/{GITHUB_CONFIG_PATH}"
GITHUB_CONFIG_API_URL = f"https://api.github.com/repos/{GITHUB_CONFIG_REPO}/contents/{GITHUB_CONFIG_PATH}"

STYLES = """
<style>
    .main { background-color: #f0f4ff; }
    .block-container { padding: 2rem 3rem; }
    .page-title { font-size: 1.8rem; font-weight: 700; color: #2563eb; margin-bottom: 0.2rem; }
    .page-subtitle { font-size: 0.95rem; color: #64748b; margin-bottom: 1.5rem; }
    .login-title { font-size: 1.4rem; font-weight: 700; color: #2563eb; margin-bottom: 0.3rem; text-align: center; }
    .login-subtitle { font-size: 0.85rem; color: #64748b; text-align: center; margin-bottom: 1.5rem; }
    .repo-card {
        background: #ffffff; border: 1px solid #bfdbfe;
        border-radius: 10px; padding: 1rem 1.4rem;
        margin-bottom: 0.75rem; transition: box-shadow 0.2s;
    }
    .repo-card:hover { box-shadow: 0 4px 14px rgba(37,99,235,0.1); }
    .repo-name { font-size: 1rem; font-weight: 600; color: #1d4ed8; text-decoration: none; }
    .repo-name:hover { text-decoration: underline; }
    .repo-desc { font-size: 0.85rem; color: #64748b; margin-top: 0.4rem; }
    .repo-meta { display: flex; flex-wrap: wrap; gap: 1.2rem; font-size: 0.8rem; color: #64748b; margin-top: 0.6rem; }
    .repo-meta span { white-space: nowrap; }
    .repo-meta-label { color: #94a3b8; margin-right: 3px; }
    .badge { display: inline-block; padding: 2px 10px; border-radius: 12px; font-size: 0.75rem; font-weight: 500; margin-right: 6px; }
    .badge-private { background: #fee2e2; color: #dc2626; }
    .badge-public  { background: #dcfce7; color: #16a34a; }
    .badge-lang    { background: #dbeafe; color: #2563eb; }
    .divider { border: none; border-top: 1px solid #bfdbfe; margin: 1.2rem 0; }
    .pagination-info { font-size: 0.85rem; color: #64748b; text-align: center; margin-top: 0.5rem; }
    .stButton > button {
        background-color: #2563eb; color: #ffffff; border: none;
        border-radius: 6px; padding: 0.35rem 1rem; font-size: 0.85rem;
        font-weight: 500; cursor: pointer; width: 100%;
    }
    .stButton > button:hover { background-color: #1d4ed8; }
    .stButton > button:disabled { background-color: #bfdbfe; color: #93c5fd; }
    section[data-testid="stSidebar"] { display: none; }
</style>
"""

st.markdown(STYLES, unsafe_allow_html=True)


# ── GitHub config helpers ─────────────────────────────────────────────────────

def load_github_config():
    resp = requests.get(GITHUB_CONFIG_RAW_URL)
    if resp.status_code == 200:
        return resp.json()
    return {}


def update_github_config(new_url, pat):
    headers = {"Authorization": f"token {pat}", "Accept": "application/vnd.github+json"}
    meta = requests.get(GITHUB_CONFIG_API_URL, headers=headers)
    if meta.status_code != 200:
        return False, f"Could not fetch config file metadata. Status: {meta.status_code}"
    sha = meta.json()["sha"]
    current_config = load_github_config()
    current_config["CURR_WEBHOOK_URL"] = new_url
    content = base64.b64encode(json.dumps(current_config, indent=4).encode()).decode()
    payload = {"message": f"Update CURR_WEBHOOK_URL to {new_url}", "content": content, "sha": sha}
    resp = requests.put(GITHUB_CONFIG_API_URL, headers=headers, json=payload)
    if resp.status_code in (200, 201):
        return True, None
    return False, resp.json().get("message", "Unknown error")


# ── User helpers ──────────────────────────────────────────────────────────────

def load_users():
    with open(USERS_FILE, "r") as f:
        return json.load(f)


def authenticate(username, password):
    for user in load_users():
        if user["username"] == username and user["password"] == password:
            return user
    return None


# ── GitHub repo/webhook helpers ───────────────────────────────────────────────

def fetch_repos(pat):
    headers = {"Authorization": f"token {pat}"}
    return requests.get(
        "https://api.github.com/user/repos?per_page=100&sort=updated&affiliation=owner",
        headers=headers,
    )


def webhook_exists(github_username, repo_name, pat, webhook_url):
    url = f"https://api.github.com/repos/{github_username}/{repo_name}/hooks"
    headers = {"Authorization": f"token {pat}", "Accept": "application/vnd.github+json"}
    resp = requests.get(url, headers=headers)
    if resp.status_code == 200:
        return any(h.get("config", {}).get("url") == webhook_url for h in resp.json())
    return False


def create_webhook(github_username, repo_name, pat, webhook_url):
    url = f"https://api.github.com/repos/{github_username}/{repo_name}/hooks"
    headers = {"Authorization": f"token {pat}", "Accept": "application/vnd.github+json"}
    payload = {
        "name": "web", "active": True,
        "events": ["push", "pull_request"],
        "config": {"url": webhook_url, "content_type": "application/json", "insecure_ssl": "0"},
    }
    return requests.post(url, headers=headers, json=payload)


def get_repo_webhook_id(github_username, repo_name, pat, webhook_url):
    url = f"https://api.github.com/repos/{github_username}/{repo_name}/hooks"
    headers = {"Authorization": f"token {pat}", "Accept": "application/vnd.github+json"}
    resp = requests.get(url, headers=headers)
    if resp.status_code == 200:
        for hook in resp.json():
            if hook.get("config", {}).get("url") == webhook_url:
                return hook["id"]
    return None


def patch_webhook_url(github_username, repo_name, pat, hook_id, new_url):
    url = f"https://api.github.com/repos/{github_username}/{repo_name}/hooks/{hook_id}"
    headers = {"Authorization": f"token {pat}", "Accept": "application/vnd.github+json"}
    payload = {"config": {"url": new_url, "content_type": "application/json", "insecure_ssl": "0"}}
    return requests.patch(url, headers=headers, json=payload)


# ── UI helpers ────────────────────────────────────────────────────────────────

def repo_card_html(repo):
    visibility = "Private" if repo["private"] else "Public"
    badge_class = "badge-private" if repo["private"] else "badge-public"
    lang = repo.get("language") or "N/A"
    stars = repo.get("stargazers_count", 0)
    forks = repo.get("forks_count", 0)
    watchers = repo.get("watchers_count", 0)
    open_issues = repo.get("open_issues_count", 0)
    default_branch = repo.get("default_branch", "N/A")
    license_name = (repo.get("license") or {}).get("spdx_id") or "No License"
    updated_at = repo.get("updated_at", "")[:10]
    description = repo.get("description") or "No description provided."
    return f"""
        <div class="repo-card">
            <div style="display:flex; align-items:center; gap:0.5rem; flex-wrap:wrap;">
                <a class="repo-name" href="{repo['html_url']}" target="_blank">{repo['name']}</a>
                <span class="badge {badge_class}">{visibility}</span>
                <span class="badge badge-lang">{lang}</span>
                <span class="badge" style="background:#f0fdf4;color:#15803d;">Branch: {default_branch}</span>
                <span class="badge" style="background:#fef9c3;color:#854d0e;">{license_name}</span>
            </div>
            <div class="repo-desc">{description}</div>
            <div class="repo-meta">
                <span><span class="repo-meta-label">Stars</span>{stars}</span>
                <span><span class="repo-meta-label">Forks</span>{forks}</span>
                <span><span class="repo-meta-label">Watchers</span>{watchers}</span>
                <span><span class="repo-meta-label">Open Issues</span>{open_issues}</span>
                <span><span class="repo-meta-label">Updated</span>{updated_at}</span>
            </div>
        </div>
    """


STATUS_HTML = {
    "pending":       "<div style='font-size:0.8rem;color:#94a3b8;font-weight:500;text-align:center;padding-top:20px;'>Pending</div>",
    "processing":    "<div style='font-size:0.8rem;color:#2563eb;font-weight:500;text-align:center;padding-top:20px;'>Processing...</div>",
    "added":         "<div style='font-size:0.8rem;color:#16a34a;font-weight:600;text-align:center;padding-top:20px;'>Webhook Added</div>",
    "already_exists":"<div style='font-size:0.8rem;color:#2563eb;font-weight:600;text-align:center;padding-top:20px;'>Already Exists</div>",
    "failed":        "<div style='font-size:0.8rem;color:#dc2626;font-weight:600;text-align:center;padding-top:20px;'>Failed</div>",
    "url_updated":   "<div style='font-size:0.8rem;color:#16a34a;font-weight:600;text-align:center;padding-top:20px;'>Webhook Updated</div>",
    "no_webhook":    "<div style='font-size:0.8rem;color:#94a3b8;font-weight:500;text-align:center;padding-top:20px;'>No Webhook</div>",
}


# ── Pages ─────────────────────────────────────────────────────────────────────

def show_login():
    _, center, _ = st.columns([1, 2, 1])
    with center:
        st.image("ValueMomentum_logo.png", use_container_width=True)
        st.markdown("""
            <div style="text-align:center; margin-top:0.5rem;">
                <div class="login-title">GitHub Repo Onboarding</div>
                <div class="login-subtitle">Sign in to manage and onboard your repositories</div>
            </div>
        """, unsafe_allow_html=True)

    _, center, _ = st.columns([1, 2, 1])
    with center:
        with st.form("login_form"):
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Sign In", use_container_width=True)

        if submitted:
            user = authenticate(username, password)
            if user:
                st.session_state["user"] = user
                st.session_state["repos"] = None
                st.session_state["page"] = 1
                st.rerun()
            else:
                st.error("Invalid username or password.")


def show_dashboard():
    user = st.session_state["user"]
    github_config = load_github_config()
    webhook_url = github_config.get("CURR_WEBHOOK_URL", "")

    # ── Header ────────────────────────────────────────────────────────────────
    header_col1, header_col2 = st.columns([8, 2])
    with header_col1:
        logo_col, title_col = st.columns([1, 6])
        with logo_col:
            st.image("ValueMomentum_logo.png", width=60)
        with title_col:
            st.markdown('<div class="page-title">GitHub Repository Onboarding</div>', unsafe_allow_html=True)
        st.markdown(
            f'<div class="page-subtitle">Logged in as <strong>{user["username"]}</strong> '
            f'— GitHub: <strong>{user["github_username"]}</strong></div>',
            unsafe_allow_html=True,
        )
    with header_col2:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("Sign Out", use_container_width=True):
            st.session_state.clear()
            st.rerun()

    st.markdown('<hr class="divider">', unsafe_allow_html=True)

    # ── Fetch repos ───────────────────────────────────────────────────────────
    if st.session_state.get("repos") is None:
        with st.spinner("Fetching repositories..."):
            response = fetch_repos(user["github_pat"])
        if response.status_code == 200:
            repos = response.json()
            if not repos:
                st.info("No repositories found for this account.")
                return
            st.session_state["repos"] = repos
            st.session_state["page"] = 1
        elif response.status_code == 404:
            st.error("GitHub user not found. Please verify the username in users.json.")
            return
        elif response.status_code == 403:
            st.error("GitHub API rate limit exceeded or invalid PAT.")
            return
        else:
            st.error(f"Failed to fetch repositories. Status code: {response.status_code}")
            return

    repos = st.session_state["repos"]
    total = len(repos)
    page = st.session_state.get("page", 1)
    total_pages = (total + REPOS_PER_PAGE - 1) // REPOS_PER_PAGE
    start = (page - 1) * REPOS_PER_PAGE
    end = start + REPOS_PER_PAGE
    page_repos = repos[start:end]

    # ── Toolbar ───────────────────────────────────────────────────────────────
    summary_col, onboard_all_col, update_url_col = st.columns([6, 2, 2])
    with summary_col:
        st.markdown(f"**{total} repositories found** — showing {start + 1} to {min(end, total)}")
    with onboard_all_col:
        if st.button("Onboard All Repos", use_container_width=True):
            st.session_state["onboard_all"] = True
            st.rerun()
    with update_url_col:
        if st.button("Update Webhook URL", use_container_width=True):
            st.session_state["show_update_url"] = True

    # ── Update Webhook URL dialog ─────────────────────────────────────────────
    if st.session_state.get("show_update_url"):
        st.markdown("""
            <div style="background:#ffffff;border:1px solid #bfdbfe;border-radius:10px;
                        padding:1.5rem 1.8rem;margin-bottom:1rem;
                        box-shadow:0 4px 16px rgba(37,99,235,0.08);">
                <div style="font-size:1rem;font-weight:700;color:#2563eb;margin-bottom:0.3rem;">Update Webhook URL</div>
                <div style="font-size:0.85rem;color:#64748b;">
                    Enter a new webhook URL. Submit updates the config only. Update patches all existing repo webhooks.
                </div>
            </div>
        """, unsafe_allow_html=True)

        with st.form("update_webhook_form"):
            current_url = github_config.get("CURR_WEBHOOK_URL", "")
            st.markdown(
                f"<div style='font-size:0.82rem;color:#64748b;margin-bottom:0.4rem;'>"
                f"Current URL: <code style='background:#f0f4ff;padding:2px 6px;border-radius:4px;color:#2563eb;'>{current_url}</code></div>",
                unsafe_allow_html=True,
            )
            new_url = st.text_input("New Webhook URL", placeholder="https://your-endpoint.vercel.app/webhook")
            fc1, fc2 = st.columns([1, 1])
            with fc1:
                submitted = st.form_submit_button("Submit", use_container_width=True)
            with fc2:
                cancelled = st.form_submit_button("Cancel", use_container_width=True)

        if cancelled:
            st.session_state.pop("show_update_url", None)
            st.session_state.pop("pending_new_url", None)
            st.session_state.pop("confirm_update_webhooks", None)
            st.session_state.pop("submitted_new_url", None)
            st.rerun()

        if submitted:
            if not new_url.strip():
                st.warning("Please enter a valid URL.")
            elif new_url.strip() == current_url.strip():
                st.info("The entered URL is the same as the current webhook URL. No changes made.")
            else:
                with st.spinner("Updating config on GitHub..."):
                    admin_pat = next(
                        (u["github_pat"] for u in load_users() if u["github_username"] == "shashanktu"),
                        user["github_pat"],
                    )
                    success, err = update_github_config(new_url.strip(), admin_pat)
                if success:
                    st.session_state["submitted_new_url"] = new_url.strip()
                    st.session_state["submitted_old_url"] = current_url.strip()
                else:
                    st.error(f"Failed to update config: {err}")

        # Show Update button only after a successful Submit
        if st.session_state.get("submitted_new_url"):
            pending_url = st.session_state["submitted_new_url"]
            st.markdown(
                f"<div style='background:#f0fdf4;border:1px solid #bbf7d0;border-radius:8px;padding:0.8rem 1.2rem;margin-bottom:0.6rem;'>"
                f"<div style='font-size:0.85rem;color:#15803d;'>Config updated to "
                f"<code style='background:#dcfce7;padding:2px 6px;border-radius:4px;'>{pending_url}</code>."
                f" Click <strong>Update</strong> to also patch this URL across all existing repo webhooks.</div></div>",
                unsafe_allow_html=True,
            )
            if st.button("Update", key="show_confirm_update", use_container_width=False):
                st.session_state["pending_new_url"] = pending_url
                st.session_state["confirm_update_webhooks"] = True
                st.rerun()

        # ── Confirmation popup ────────────────────────────────────────────────
        if st.session_state.get("confirm_update_webhooks"):
            pending_url = st.session_state.get("pending_new_url", "")
            st.markdown(f"""
                <div style="background:#eff6ff;border:1px solid #bfdbfe;border-radius:8px;
                            padding:1rem 1.4rem;margin-top:0.5rem;">
                    <div style="font-size:0.95rem;font-weight:600;color:#1d4ed8;margin-bottom:0.4rem;">
                        Confirm Webhook URL Update
                    </div>
                    <div style="font-size:0.85rem;color:#475569;">
                        This will patch the existing webhook URL across <strong>all repositories</strong> to:<br>
                        <code style="background:#dbeafe;padding:2px 6px;border-radius:4px;color:#1d4ed8;">{pending_url}</code>
                    </div>
                </div>
            """, unsafe_allow_html=True)
            st.markdown("<div style='margin-top:0.6rem;'></div>", unsafe_allow_html=True)
            yes_col, no_col = st.columns([1, 1])
            with yes_col:
                if st.button("Yes, Update All Webhooks", key="confirm_yes", use_container_width=True):
                    st.session_state["confirm_update_webhooks"] = False
                    st.session_state["show_update_url"] = False
                    st.session_state["bulk_update_url"] = pending_url
                    st.session_state.pop("pending_new_url", None)
                    st.session_state.pop("submitted_new_url", None)
                    st.rerun()
            with no_col:
                if st.button("No, Cancel", key="confirm_no", use_container_width=True):
                    st.session_state["confirm_update_webhooks"] = False
                    st.session_state.pop("pending_new_url", None)
                    st.rerun()

    # ── Bulk webhook URL update flow ──────────────────────────────────────────
    if st.session_state.get("bulk_update_url"):
        new_webhook_url = st.session_state.pop("bulk_update_url")
        old_webhook_url = st.session_state.pop("submitted_old_url", webhook_url)

        progress_bar = st.progress(0, text=f"Starting webhook URL update... (0/{total})")
        status_placeholders = {}
        for repo in repos:
            card_col, status_col = st.columns([9, 1.4])
            with card_col:
                st.markdown(repo_card_html(repo), unsafe_allow_html=True)
            with status_col:
                status_placeholders[repo["id"]] = st.empty()
                status_placeholders[repo["id"]].markdown(STATUS_HTML["pending"], unsafe_allow_html=True)

        updated, skipped, failed = 0, 0, 0
        for i, repo in enumerate(repos):
            progress_bar.progress((i + 1) / total, text=f"Updating {repo['name']} ({i + 1}/{total})")
            status_placeholders[repo["id"]].markdown(STATUS_HTML["processing"], unsafe_allow_html=True)

            hook_id = get_repo_webhook_id(user["github_username"], repo["name"], user["github_pat"], old_webhook_url)
            if hook_id is None:
                # No existing webhook — create a new one with the new URL
                result = create_webhook(user["github_username"], repo["name"], user["github_pat"], new_webhook_url)
                if result.status_code in (200, 201):
                    updated += 1
                    status_placeholders[repo["id"]].markdown(STATUS_HTML["added"], unsafe_allow_html=True)
                else:
                    failed += 1
                    status_placeholders[repo["id"]].markdown(STATUS_HTML["failed"], unsafe_allow_html=True)
            else:
                result = patch_webhook_url(user["github_username"], repo["name"], user["github_pat"], hook_id, new_webhook_url)
                if result.status_code == 200:
                    updated += 1
                    status_placeholders[repo["id"]].markdown(STATUS_HTML["url_updated"], unsafe_allow_html=True)
                else:
                    failed += 1
                    status_placeholders[repo["id"]].markdown(STATUS_HTML["failed"], unsafe_allow_html=True)

        progress_bar.progress(1.0, text=f"Update complete. ({total}/{total})")
        st.success(f"Webhook URL update complete — Updated: {updated}, Skipped (no webhook): {skipped}, Failed: {failed}")
        st.stop()

    # ── Onboard All flow ──────────────────────────────────────────────────────
    if st.session_state.get("onboard_all"):
        st.session_state["onboard_all"] = False
        onboarded = st.session_state.setdefault("onboarded", set())
        webhook_status = st.session_state.setdefault("webhook_status", {})

        progress_bar = st.progress(0, text=f"Starting onboarding... (0/{total})")
        status_placeholders = {}
        for repo in repos:
            card_col, status_col = st.columns([9, 1.4])
            with card_col:
                st.markdown(repo_card_html(repo), unsafe_allow_html=True)
            with status_col:
                status_placeholders[repo["id"]] = st.empty()
                status_placeholders[repo["id"]].markdown(STATUS_HTML["pending"], unsafe_allow_html=True)

        for i, repo in enumerate(repos):
            progress_bar.progress((i + 1) / total, text=f"Processing {repo['name']} ({i + 1}/{total})")
            status_placeholders[repo["id"]].markdown(STATUS_HTML["processing"], unsafe_allow_html=True)

            if webhook_exists(user["github_username"], repo["name"], user["github_pat"], webhook_url):
                onboarded.add(repo["id"])
                webhook_status[repo["id"]] = "already_exists"
                status_placeholders[repo["id"]].markdown(STATUS_HTML["already_exists"], unsafe_allow_html=True)
            else:
                result = create_webhook(user["github_username"], repo["name"], user["github_pat"], webhook_url)
                if result.status_code in (200, 201):
                    onboarded.add(repo["id"])
                    webhook_status[repo["id"]] = "added"
                    status_placeholders[repo["id"]].markdown(STATUS_HTML["added"], unsafe_allow_html=True)
                else:
                    webhook_status[repo["id"]] = "failed"
                    status_placeholders[repo["id"]].markdown(STATUS_HTML["failed"], unsafe_allow_html=True)

        progress_bar.progress(1.0, text=f"Onboarding complete. ({total}/{total})")
        st.success(f"Onboarding complete for all {total} repositories.")
        st.stop()

    # ── Normal paginated list ─────────────────────────────────────────────────
    st.markdown("")
    for repo in page_repos:
        card_col, btn_col = st.columns([9, 1.4])
        with card_col:
            st.markdown(repo_card_html(repo), unsafe_allow_html=True)
        with btn_col:
            st.markdown("<div style='height:18px'></div>", unsafe_allow_html=True)
            wh_status = st.session_state.get("webhook_status", {}).get(repo["id"])
            already_onboarded = repo["id"] in st.session_state.get("onboarded", set())

            if wh_status in STATUS_HTML and wh_status not in ("pending", "processing"):
                st.markdown(STATUS_HTML[wh_status], unsafe_allow_html=True)
            else:
                btn_label = "Onboarded" if already_onboarded else "Onboard"
                if st.button(btn_label, key=f"onboard_{repo['id']}", use_container_width=True, disabled=already_onboarded):
                    with st.spinner(f"Creating webhook for {repo['name']}..."):
                        if webhook_exists(user["github_username"], repo["name"], user["github_pat"], webhook_url):
                            st.session_state.setdefault("onboarded", set()).add(repo["id"])
                            st.session_state.setdefault("webhook_status", {})[repo["id"]] = "already_exists"
                        else:
                            result = create_webhook(user["github_username"], repo["name"], user["github_pat"], webhook_url)
                            if result.status_code in (200, 201):
                                st.session_state.setdefault("onboarded", set()).add(repo["id"])
                                st.session_state.setdefault("webhook_status", {})[repo["id"]] = "added"
                            elif result.status_code == 404:
                                st.error(f"Repository '{repo['name']}' not found or insufficient permissions.")
                            else:
                                st.session_state.setdefault("webhook_status", {})[repo["id"]] = "failed"
                                st.error(f"Failed to create webhook. Status: {result.status_code} — {result.json().get('message', '')}")
                    st.rerun()

    st.markdown('<hr class="divider">', unsafe_allow_html=True)

    nav_col1, nav_col2, nav_col3 = st.columns([1, 4, 1])
    with nav_col1:
        if st.button("Previous", disabled=(page <= 1), use_container_width=True):
            st.session_state["page"] -= 1
            st.rerun()
    with nav_col2:
        st.markdown(f'<div class="pagination-info">Page {page} of {total_pages}</div>', unsafe_allow_html=True)
    with nav_col3:
        if st.button("Next", disabled=(page >= total_pages), use_container_width=True):
            st.session_state["page"] += 1
            st.rerun()


if "user" not in st.session_state:
    show_login()
else:
    show_dashboard()
