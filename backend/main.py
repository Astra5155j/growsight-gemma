from __future__ import annotations

import asyncio
import ipaddress
import socket
from pathlib import Path
from urllib.parse import urlparse

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from backend.audit import make_rule_audit
from backend.ollama_client import analyze_with_gemma
from backend.scanner import WebsiteScanError, scan_website

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = BASE_DIR / "frontend"

app = FastAPI(
    title="GrowSight",
    description="Local Gemma-powered website growth auditor",
    version="1.0.0",
)
app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")


class AuditRequest(BaseModel):
    url: str = Field(min_length=4, max_length=2048)
    use_ai: bool = True
    analyze_screenshots: bool = True


def _is_global_address(raw_ip: str) -> bool:
    try:
        return ipaddress.ip_address(raw_ip).is_global
    except ValueError:
        return False


def validate_public_url(raw_url: str) -> str:
    url = raw_url.strip()
    if not url:
        raise ValueError("Enter a website URL.")
    if "://" not in url:
        url = "https://" + url
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError("Only public HTTP and HTTPS websites are supported.")
    if not parsed.hostname:
        raise ValueError("That does not look like a valid website URL.")
    if parsed.username or parsed.password:
        raise ValueError("URLs containing usernames or passwords are not allowed.")

    host = parsed.hostname.rstrip(".").lower()
    if host == "localhost" or host.endswith(".localhost"):
        raise ValueError("Localhost URLs cannot be scanned.")
    if "." not in host and not _is_global_address(host):
        raise ValueError("Enter a public website hostname.")

    try:
        infos = socket.getaddrinfo(
            host,
            parsed.port or (443 if parsed.scheme == "https" else 80),
            type=socket.SOCK_STREAM,
        )
    except (socket.gaierror, OSError):
        raise ValueError("Could not resolve that hostname. Check the URL and try again.")

    if not infos:
        raise ValueError("That hostname did not resolve.")
    for info in infos:
        if not _is_global_address(info[4][0]):
            raise ValueError("This URL resolves to a private or reserved network address and cannot be scanned.")

    # Drop fragment because it is not sent to the server.
    return url.split("#", 1)[0]


@app.get("/")
async def index():
    return FileResponse(FRONTEND_DIR / "index.html")


@app.get("/api/health")
async def health():
    return {"status": "ok", "app": "GrowSight", "ai_provider": "Ollama", "default_model": "gemma3:4b"}


@app.post("/api/audit")
async def audit(req: AuditRequest):
    try:
        safe_url = validate_public_url(req.url)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    try:
        scan = await asyncio.to_thread(scan_website, safe_url)
    except WebsiteScanError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception as exc:
        # Return a useful but non-sensitive error rather than a generic Playwright TypeError.
        raise HTTPException(
            status_code=500,
            detail=f"Scanner error ({type(exc).__name__}): {str(exc)[:300] or 'No additional details'}. Check Playwright installation.",
        )

    report = make_rule_audit(safe_url, scan)
    if req.use_ai:
        report = await analyze_with_gemma(report, analyze_screenshots=req.analyze_screenshots)
    else:
        report["ai"] = {
            "used": False,
            "provider": "None",
            "model": None,
            "status": "AI disabled; rule-based audit only",
        }
    return report
