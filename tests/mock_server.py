"""A tiny in-process HTTP server that mimics the lolz.live Forum API.

It implements just enough of the API for end-to-end testing of the bot:

* ``GET  /users/me``
* ``GET  /threads?forum_id=...``
* ``POST /posts``  (records the created post)

Requests without a valid ``Authorization: Bearer`` header get ``401``.
"""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse


def make_threads(forum_id, titles, creator_user_id=999):
    threads = []
    for idx, title in enumerate(titles, start=1):
        threads.append(
            {
                "thread_id": forum_id * 100 + idx,
                "forum_id": forum_id,
                "thread_title": title,
                "creator_user_id": creator_user_id,
                "creator_username": "op_user",
            }
        )
    return threads


class MockLolzServer:
    """Context manager that runs the mock API and collects created posts."""

    def __init__(self, threads_by_forum, token="valid-token", me_id=1):
        self.threads_by_forum = threads_by_forum
        self.token = token
        self.me_id = me_id
        self.created_posts = []
        self._server = None
        self._thread = None

    @property
    def base_url(self):
        host, port = self._server.server_address
        return f"http://127.0.0.1:{port}"

    def __enter__(self):
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):  # silence
                pass

            def _authorized(self):
                auth = self.headers.get("Authorization", "")
                return auth == f"Bearer {outer.token}"

            def _send(self, status, payload):
                body = json.dumps(payload).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_GET(self):
                parsed = urlparse(self.path)
                if not self._authorized():
                    return self._send(401, {"errors": ["Unauthorized"]})
                if parsed.path == "/users/me":
                    return self._send(200, {"user": {"user_id": outer.me_id,
                                                      "username": "bot_user"}})
                if parsed.path == "/threads":
                    qs = parse_qs(parsed.query)
                    forum_id = int(qs.get("forum_id", [0])[0])
                    page = int(qs.get("page", [1])[0])
                    threads = outer.threads_by_forum.get(forum_id, []) if page == 1 else []
                    return self._send(200, {"threads": threads,
                                            "threads_total": len(threads)})
                return self._send(404, {"errors": ["Not found"]})

            def do_POST(self):
                if not self._authorized():
                    return self._send(401, {"errors": ["Unauthorized"]})
                if urlparse(self.path).path == "/posts":
                    length = int(self.headers.get("Content-Length", 0))
                    raw = self.rfile.read(length).decode("utf-8")
                    fields = parse_qs(raw)
                    thread_id = int(fields.get("thread_id", [0])[0])
                    post_body = fields.get("post_body", [""])[0]
                    if not post_body.strip():
                        return self._send(403, {"errors": ["Empty post"]})
                    post_id = 5000 + len(outer.created_posts) + 1
                    outer.created_posts.append(
                        {"thread_id": thread_id, "post_body": post_body,
                         "post_id": post_id}
                    )
                    return self._send(200, {"post": {"post_id": post_id,
                                                     "thread_id": thread_id,
                                                     "post_body": post_body}})
                return self._send(404, {"errors": ["Not found"]})

        self._server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        return self

    def __exit__(self, *exc):
        self._server.shutdown()
        self._server.server_close()
        self._thread.join(timeout=5)
