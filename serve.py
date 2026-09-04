#!/usr/bin/env python3
"""Local site server with project-photo upload."""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from datetime import datetime, timezone
import mimetypes
import os
import re
import uuid
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

ROOT = Path(__file__).resolve().parent
PHOTOS = ROOT / "images" / "projects"
CAPTIONS = PHOTOS / "captions.json"
ALLOWED = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
SAFE = re.compile(r"[^a-zA-Z0-9._-]+")


def load_captions():
    if not CAPTIONS.exists():
        return {}
    try:
        data = json.loads(CAPTIONS.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except json.JSONDecodeError:
        return {}


def save_captions(data):
    PHOTOS.mkdir(parents=True, exist_ok=True)
    CAPTIONS.write_text(json.dumps(data, indent=2), encoding="utf-8")


def list_photos():
    PHOTOS.mkdir(parents=True, exist_ok=True)
    caps = load_captions()
    files = [
        p.name
        for p in sorted(PHOTOS.iterdir(), key=lambda x: x.stat().st_mtime)
        if p.is_file() and p.suffix.lower() in ALLOWED
    ]
    return [{"name": name, "caption": (caps.get(name) or "").strip()} for name in files]



CONTACT_TO = "info@ledfordllc.com"
CONTACT_LOG = ROOT / "contact-submissions.jsonl"


def send_contact(payload: dict) -> None:
    first = (payload.get("first") or "").strip()
    last = (payload.get("last") or "").strip()
    email = (payload.get("email") or "").strip()
    phone = (payload.get("phone") or "").strip()
    company = (payload.get("company") or "").strip()
    project = (payload.get("project") or "").strip()
    location = (payload.get("location") or "").strip()
    bid_due = (payload.get("bid_due") or "").strip()
    trades = (payload.get("trades") or "").strip()
    help_text = (payload.get("help") or "").strip()
    if not email or not help_text:
        raise ValueError("Email and message are required.")
    name = (first + " " + last).strip() or "Website visitor"
    message = (
        f"From: {name}\n"
        f"Email: {email}\n"
        f"Phone: {phone or '—'}\n"
        f"Company / GC: {company or '—'}\n"
        f"Project: {project or '—'}\n"
        f"City / site: {location or '—'}\n"
        f"Bid due: {bid_due or '—'}\n"
        f"Trades: {trades or '—'}\n\n"
        f"{help_text}"
    )
    record = {
        "at": datetime.now(timezone.utc).isoformat(),
        "to": CONTACT_TO,
        "first": first,
        "last": last,
        "email": email,
        "phone": phone,
        "company": company,
        "project": project,
        "location": location,
        "bid_due": bid_due,
        "trades": trades,
        "help": help_text,
    }
    with CONTACT_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")
    body = json.dumps({
        "name": name,
        "email": email,
        "_replyto": email,
        "_subject": f"Bid request: {project or name}",
        "message": message,
        "_captcha": "false",
    }).encode()
    req = urllib.request.Request(
        f"https://formsubmit.co/ajax/{CONTACT_TO}",
        data=body,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            resp.read()
    except urllib.error.HTTPError as e:
        # FormSubmit returns 200 after activation; still keep the local log.
        raise RuntimeError(e.read().decode("utf-8", "ignore")[:400]) from e


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/projects":
            body = json.dumps(list_photos()).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        return super().do_GET()

    def do_DELETE(self):
        parsed = urlparse(self.path)
        if not parsed.path.startswith("/api/projects/"):
            self.send_error(404)
            return
        name = SAFE.sub("", unquote(parsed.path.split("/")[-1]))
        target = PHOTOS / name
        if not target.exists() or not target.is_file():
            self.send_error(404)
            return
        target.unlink()
        caps = load_captions()
        if name in caps:
            caps.pop(name, None)
            save_captions(caps)
        body = b'{"ok":true}'
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _json(self, code, obj):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        parsed = urlparse(self.path)
        ctype = self.headers.get("Content-Type", "")
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length)
        if parsed.path == "/api/caption":
            try:
                payload = json.loads(raw.decode("utf-8") or "{}")
                name = SAFE.sub("", payload.get("file") or "")
                caption = (payload.get("caption") or "").strip()[:280]
                if not name or not (PHOTOS / name).is_file():
                    return self._json(404, {"ok": False, "error": "Photo not found."})
                caps = load_captions()
                if caption:
                    caps[name] = caption
                else:
                    caps.pop(name, None)
                save_captions(caps)
            except Exception as e:
                return self._json(400, {"ok": False, "error": str(e)})
            return self._json(200, {"ok": True, "file": name, "caption": caption})
        if parsed.path == "/api/contact":
            try:
                payload = json.loads(raw.decode("utf-8") or "{}")
                send_contact(payload)
            except ValueError as e:
                return self._json(400, {"ok": False, "error": str(e)})
            except Exception as e:
                return self._json(502, {"ok": False, "error": str(e)})
            return self._json(200, {"ok": True, "to": CONTACT_TO})
        if parsed.path != "/api/projects":
            self.send_error(404)
            return
        saved = []
        if "multipart/form-data" in ctype:
            boundary = None
            for part in ctype.split(";"):
                part = part.strip()
                if part.startswith("boundary="):
                    boundary = part.split("=", 1)[1].strip().strip('"')
            if not boundary:
                self.send_error(400, "Missing boundary")
                return
            saved = self._save_multipart(raw, boundary.encode())
        else:
            self.send_error(400, "Use multipart form upload")
            return
        self._json(200, {"ok": True, "files": saved})

    def _save_multipart(self, raw: bytes, boundary: bytes):
        PHOTOS.mkdir(parents=True, exist_ok=True)
        saved = []
        parts = raw.split(b"--" + boundary)
        for part in parts:
            if not part or part in (b"--\r\n", b"--"):
                continue
            header, _, data = part.partition(b"\r\n\r\n")
            if not data:
                continue
            if data.endswith(b"\r\n"):
                data = data[:-2]
            header_text = header.decode("utf-8", "ignore")
            if "filename=" not in header_text:
                continue
            fname = header_text.split("filename=")[-1].split("\r\n")[0].strip().strip('"')
            ext = Path(fname).suffix.lower()
            if ext not in ALLOWED:
                continue
            stem = SAFE.sub("-", Path(fname).stem)[:40] or "photo"
            out = PHOTOS / f"{stem}-{uuid.uuid4().hex[:8]}{ext}"
            out.write_bytes(data)
            saved.append(out.name)
        return saved

    def log_message(self, fmt, *args):
        print("[%s] %s" % (self.log_date_time_string(), fmt % args))


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8765"))
    httpd = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    print(f"Serving {ROOT} on http://127.0.0.1:{port}")
    httpd.serve_forever()
