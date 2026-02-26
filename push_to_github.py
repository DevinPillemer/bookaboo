#!/usr/bin/env python3
"""Push Bookaboo project files to GitHub via the REST API."""

import argparse
import base64
import json
import os
import sys
import urllib.request
import urllib.error

OWNER = "DevinPillemer"
REPO = "bookaboo"
BRANCH = "main"
BASE_URL = f"https://api.github.com/repos/{OWNER}/{REPO}"

# The 15 project files to push (relative to /home/user)
FILES = [
    ".env.example",
    ".gitignore",
    "Dockerfile",
    "README.md",
    "api_server.py",
    "bookaboo.py",
    "calendar_integration.py",
    "config/user_profile.json",
    "nlp_parser.py",
    "notifications.py",
    "ontopo_client.py",
    "requirements.txt",
    "reserve.py",
    "test_bookaboo.py",
    "user_profile.py",
]

ROOT = "/home/user"


def api_request(token: str, method: str, path: str, body: dict = None):
    url = f"{BASE_URL}/{path}"
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read()), resp.status
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        return json.loads(body) if body else {}, e.code


def get_existing_sha(token: str, path: str) -> str | None:
    """Return the blob SHA of a file already in the repo, or None."""
    result, status = api_request(token, "GET", f"contents/{path}?ref={BRANCH}")
    if status == 200:
        return result.get("sha")
    return None


def ensure_repo_exists(token: str):
    """Create the repo if it doesn't exist yet; proceed silently if it does."""
    result, status = api_request(token, "GET", "")
    if status == 200:
        print(f"  Repo {OWNER}/{REPO} already exists.")
        return
    # Attempt creation regardless (handles 404 or token-scope edge cases)
    print(f"  Checking/creating repo {OWNER}/{REPO}...")
    create_url = "https://api.github.com/user/repos"
    body = {"name": REPO, "private": False, "auto_init": False}
    data = json.dumps(body).encode()
    req = urllib.request.Request(
        create_url,
        data=data,
        method="POST",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req) as resp:
            print(f"  Repo created (HTTP {resp.status}).")
    except urllib.error.HTTPError as e:
        body_text = e.read().decode()
        err = json.loads(body_text) if body_text else {}
        # 422 "name already exists" means repo is present — that's fine
        if e.code == 422 and "already exists" in body_text:
            print(f"  Repo already exists — proceeding.")
        else:
            print(f"  Failed to create repo: {body_text}", file=sys.stderr)
            sys.exit(1)


def push_file(token: str, rel_path: str) -> bool:
    local_path = os.path.join(ROOT, rel_path)
    if not os.path.exists(local_path):
        print(f"  SKIP  {rel_path}  (not found locally)")
        return False

    with open(local_path, "rb") as f:
        content_b64 = base64.b64encode(f.read()).decode()

    sha = get_existing_sha(token, rel_path)

    payload = {
        "message": f"feat: add {rel_path}",
        "content": content_b64,
        "branch": BRANCH,
    }
    if sha:
        payload["sha"] = sha
        action = "UPDATE"
    else:
        action = "CREATE"

    result, status = api_request(token, "PUT", f"contents/{rel_path}", payload)
    if status in (200, 201):
        print(f"  OK    [{action}] {rel_path}")
        return True
    else:
        msg = result.get("message", json.dumps(result))
        print(f"  FAIL  {rel_path}  →  HTTP {status}: {msg}", file=sys.stderr)
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Push Bookaboo project files to GitHub via REST API."
    )
    parser.add_argument("token", help="GitHub personal access token (needs repo scope)")
    args = parser.parse_args()

    token = args.token.strip()
    print(f"Target: https://github.com/{OWNER}/{REPO}  (branch: {BRANCH})")
    print()

    ensure_repo_exists(token)
    print()

    ok = fail = 0
    for rel_path in FILES:
        if push_file(token, rel_path):
            ok += 1
        else:
            fail += 1

    print()
    print(f"Done. {ok} succeeded, {fail} failed.")
    if fail:
        sys.exit(1)


if __name__ == "__main__":
    main()
