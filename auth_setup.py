#!/usr/bin/env python3
"""
One-time interactive OAuth setup for the Yoto API.

Run this on a machine with a browser (the Beelink is headless). It performs an
Authorization Code + PKCE flow against Yoto's Auth0-backed login server via a
temporary local loopback redirect (http://127.0.0.1:<port>/callback), then
writes the resulting refresh token into data/state.json.

Yoto's own docs (yoto.dev/authentication/headless-cli-auth) point CLI/native
apps at PKCE-loopback rather than the older device-code flow, so that's what
this implements.

Usage:
    python auth_setup.py --client-id YOUR_YOTO_CLIENT_ID
"""
import argparse
import base64
import hashlib
import http.server
import os
import secrets
import sys
import threading
import time
import urllib.parse
import webbrowser

import requests

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))
from state import State  # noqa: E402

AUTH_BASE = os.environ.get("YOTO_AUTH_BASE", "https://login.yotoplay.com")
AUDIENCE = os.environ.get("YOTO_AUDIENCE", "https://api.yotoplay.com")
SCOPE = os.environ.get(
    "YOTO_SCOPE",
    "offline_access user:content:manage user:content:view user:icons:manage",
)


def b64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


CALLBACK_PORT = int(os.environ.get("YOTO_CALLBACK_PORT", "8765"))


class _CallbackServer:
    """Single-shot local HTTP server that captures the OAuth redirect."""

    def __init__(self):
        self.result = {}
        handler = self._make_handler()
        self.httpd = http.server.HTTPServer(("127.0.0.1", CALLBACK_PORT), handler)
        self.port = self.httpd.server_address[1]

    def _make_handler(self):
        outer = self

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                parsed = urllib.parse.urlparse(self.path)
                params = urllib.parse.parse_qs(parsed.query)
                outer.result["code"] = params.get("code", [None])[0]
                outer.result["state"] = params.get("state", [None])[0]
                outer.result["error"] = params.get("error_description", params.get("error", [None]))[0]

                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.end_headers()
                if outer.result.get("error"):
                    body = f"<html><body><h2>Yoto auth failed</h2><p>{outer.result['error']}</p></body></html>"
                else:
                    body = "<html><body><h2>Yoto auth complete</h2><p>You can close this window.</p></body></html>"
                self.wfile.write(body.encode("utf-8"))

            def log_message(self, *args):
                pass  # silence default request logging

        return Handler

    @property
    def redirect_uri(self):
        return f"http://127.0.0.1:{self.port}/callback"

    def wait_for_callback(self, timeout=300):
        self.httpd.timeout = timeout
        self.httpd.handle_request()
        return self.result


def run(client_id: str, state_path: str):
    code_verifier = b64url(os.urandom(64))
    code_challenge = b64url(hashlib.sha256(code_verifier.encode("ascii")).digest())
    csrf_state = secrets.token_urlsafe(16)

    server = _CallbackServer()

    authorize_url = AUTH_BASE + "/authorize?" + urllib.parse.urlencode({
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": server.redirect_uri,
        "scope": SCOPE,
        "audience": AUDIENCE,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
        "state": csrf_state,
    })

    print(f"Opening browser for Yoto login:\n  {authorize_url}\n")
    print(f"Waiting for redirect on {server.redirect_uri} ...")
    webbrowser.open(authorize_url)

    result = server.wait_for_callback()

    if result.get("error"):
        print(f"Auth failed: {result['error']}", file=sys.stderr)
        sys.exit(1)
    if not result.get("code"):
        print("No authorization code received (timed out?).", file=sys.stderr)
        sys.exit(1)
    if result.get("state") != csrf_state:
        print("State mismatch — possible CSRF, aborting.", file=sys.stderr)
        sys.exit(1)

    token_resp = requests.post(
        AUTH_BASE + "/oauth/token",
        json={
            "grant_type": "authorization_code",
            "client_id": client_id,
            "code_verifier": code_verifier,
            "code": result["code"],
            "redirect_uri": server.redirect_uri,
        },
        timeout=30,
    )
    token_resp.raise_for_status()
    tokens = token_resp.json()

    refresh_token = tokens.get("refresh_token")
    if not refresh_token:
        print(
            "Token response did not include a refresh_token — make sure the "
            "Yoto client is a public client with offline_access enabled.",
            file=sys.stderr,
        )
        print(tokens, file=sys.stderr)
        sys.exit(1)

    state = State(state_path)
    state.update(
        yoto_client_id=client_id,
        yoto_refresh_token=refresh_token,
        yoto_access_token=tokens.get("access_token"),
        yoto_access_token_expires_at=time.time() + float(tokens.get("expires_in", 0)),
    )

    print(f"Success. Refresh token saved to {state_path}")
    print("Copy this file to the Beelink at data/state.json.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--client-id",
        default=os.environ.get("YOTO_CLIENT_ID", ""),
        required=not os.environ.get("YOTO_CLIENT_ID"),
        help="Yoto public client ID (from yoto.dev)",
    )
    parser.add_argument(
        "--state-file",
        default=os.path.join(os.path.dirname(__file__), "data", "state.json"),
        help="Where to write the resulting refresh token (default: data/state.json)",
    )
    args = parser.parse_args()
    run(args.client_id, args.state_file)
