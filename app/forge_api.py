from __future__ import annotations

import json
import secrets
import threading
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Callable


API_BASE_URL = "https://api.core-utils.dev"
REQUEST_TIMEOUT = 12


class ForgeApiError(RuntimeError):
    pass


@dataclass(frozen=True)
class ForgeUser:
    id: int
    github_login: str
    display_name: str | None
    avatar_url: str | None
    role: str


def _json_request(path: str, *, method: str = "GET", token: str | None = None, payload: dict[str, Any] | None = None) -> Any:
    data = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(f"{API_BASE_URL}{path}", data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT) as response:
            if response.status == 204:
                return None
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        try:
            body = json.loads(exc.read().decode("utf-8"))
            detail = body.get("detail", exc.reason)
        except Exception:
            detail = exc.reason
        raise ForgeApiError(str(detail)) from exc
    except Exception as exc:
        raise ForgeApiError(str(exc)) from exc


class ForgeApiClient:
    def __init__(self, token: str | None = None) -> None:
        self.token = token

    def me(self) -> ForgeUser:
        data = _json_request("/api/auth/me", token=self.token)
        return ForgeUser(
            id=int(data["id"]),
            github_login=str(data["github_login"]),
            display_name=data.get("display_name"),
            avatar_url=data.get("avatar_url"),
            role=str(data.get("role", "user")),
        )

    def list_threads(
        self,
        *,
        tool_slug: str | None = None,
        q: str | None = None,
        sort: str = "recent",
        page: int = 1,
        page_size: int = 20,
    ) -> dict[str, Any]:
        params: dict[str, str] = {"sort": sort, "page": str(page), "page_size": str(page_size)}
        if tool_slug:
            params["tool_slug"] = tool_slug
        if q:
            params["q"] = q
        return _json_request(f"/api/forge/threads?{urllib.parse.urlencode(params)}", token=self.token)

    def list_comments(self, thread_id: int) -> dict[str, Any]:
        return _json_request(f"/api/forge/threads/{thread_id}/comments", token=self.token)

    def create_comment(self, thread_id: int, body: str) -> dict[str, Any]:
        return _json_request(
            f"/api/forge/threads/{thread_id}/comments",
            method="POST",
            token=self.token,
            payload={"body": body},
        )


def run_desktop_login(on_result: Callable[[str | None, str | None], None]) -> None:
    nonce = secrets.token_urlsafe(16)
    completed = threading.Event()

    class CallbackHandler(BaseHTTPRequestHandler):
        def log_message(self, _format: str, *_args: object) -> None:
            return

        def do_GET(self) -> None:
            parsed = urllib.parse.urlparse(self.path)
            params = dict(urllib.parse.parse_qsl(parsed.query))
            token = params.get("token")
            state = params.get("state")
            if token and state == nonce:
                completed.set()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(b"<html><body><h1>Core Utils Desktop login complete</h1><p>You can close this tab.</p></body></html>")
                on_result(token, None)
            else:
                completed.set()
                self.send_response(400)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(b"<html><body><h1>Login failed</h1></body></html>")
                on_result(None, "Login callback did not include a valid token.")
            threading.Thread(target=self.server.shutdown, daemon=True).start()

    server = ThreadingHTTPServer(("127.0.0.1", 0), CallbackHandler)
    redirect_uri = f"http://127.0.0.1:{server.server_port}/callback"
    login_url = (
        f"{API_BASE_URL}/api/auth/github/desktop-login?"
        f"{urllib.parse.urlencode({'redirect_uri': redirect_uri, 'nonce': nonce})}"
    )
    webbrowser.open(login_url)
    def timeout() -> None:
        if not completed.is_set():
            completed.set()
            on_result(None, "Login timed out.")
        server.shutdown()

    timer = threading.Timer(120, timeout)
    timer.daemon = True
    timer.start()
    server.serve_forever()
    timer.cancel()
    server.server_close()
