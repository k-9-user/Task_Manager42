"""make smoke: read-only HTTPS checks of health, frontend and API routes."""

import base64
import hashlib
import json
import re

from ..lib.paths import CERT
from ..lib.process import require, run

OPENAPI_OPERATIONS = {
    "/health": "get", "/api/auth/login": "post", "/api/auth/register": "post",
    "/api/projects": "get", "/api/tasks/{task_id}": "put",
    "/api/notifications": "get", "/api/search/tasks": "get", "/api/gdpr/export": "get",
    "/api/users/me": "get", "/api/v1/public/tasks": "get", "/api/status": "get",
    "/api/export": "get", "/api/import": "post",
    "/api/tasks/{task_id}/attachments": "post", "/api/attachments/{attachment_id}": "delete",
    "/api/auth/oauth/google/exchange": "post", "/api/api-keys": "post",
    "/api/api-keys/{key_id}/rotate": "post",
}


def smoke():
    def get(path, *, with_headers=False):
        output = run([
            "curl", "--fail", "--silent", "--show-error", "--noproxy", "*",
            "--connect-timeout", "5", "--max-time", "15", "--cacert", str(CERT),
        ] + (["--include"] if with_headers else []) + [
            "https://localhost" + path,
        ], quiet=True)
        if not with_headers:
            return output
        for separator in ("\r\n\r\n", "\n\n"):
            headers, found, body = output.partition(separator)
            if found:
                return headers, body
        raise ValueError("Frontend response has no header/body separator")

    def frontend_nonce():
        """Prove the CSP nonce pipeline end to end."""

        headers, body = get("/", with_headers=True)
        require("VITE_CSP_NONCE" not in body, "nginx did not substitute the Vite CSP nonce placeholder")
        policy = re.search(r"(?im)^content-security-policy:.*$", headers)
        require(policy is not None, "Frontend response carries no Content-Security-Policy")
        declared = re.search(r"'nonce-([A-Za-z0-9+/=_-]+)'", policy.group(0))
        require(declared is not None, "Frontend CSP declares no nonce source")
        tags = re.findall(r"<script\b[^>]*>", body)
        require(tags and all('nonce="' in tag for tag in tags), "A script tag is not nonced; it would be blocked by script-src")
        stamped = set(re.findall(r'nonce="([A-Za-z0-9+/=_-]+)"', body))
        require(stamped == {declared.group(1)}, "Vite tag nonces do not match the nonce declared in the CSP header")
        return declared.group(1)

    def docs_scripts():
        """Prove every script on /docs is allowed by the /docs CSP."""

        headers, body = get("/docs", with_headers=True)
        policy = re.search(r"(?im)^content-security-policy:.*$", headers)
        require(policy is not None, "Docs response carries no Content-Security-Policy")
        declared = re.search(r"script-src ([^;]*)", policy.group(0))
        require(declared is not None, "Docs CSP declares no script-src")
        sources = declared.group(1).split()
        scripts = re.findall(r"<script\b([^>]*)>(.*?)</script>", body, re.S)
        require(scripts, "Docs page has no script")
        for attributes, code in scripts:
            src = re.search(r'src="([^"]+)"', attributes)
            if src:
                allowed = any(source.startswith("https://") and src.group(1).startswith(source) for source in sources)
                require(allowed, "Docs page loads a script its CSP does not allow")
            else:
                digest = base64.b64encode(hashlib.sha256(code.encode()).digest()).decode()
                require(f"'sha256-{digest}'" in sources, "Docs inline script hash is missing from the /docs CSP; update nginx/default.conf")

    require(json.loads(get("/health")) == {"status": "ok", "db": "ok"}, "Health check failed")
    root = get("/")
    require('<div id="root">' in root and re.search(r'src="/src/main\.jsx(\?t=\d+)?"', root), "Frontend root or source entry is missing")
    require(frontend_nonce() != frontend_nonce(), "Frontend CSP nonce is not unique per request")
    entry = get("/src/main.jsx")
    require("/node_modules/.vite/deps/" in entry and "/src/App.jsx" in entry and "createRoot" in entry and "<StrictMode>" not in entry, "Frontend entry is not Vite-transformed JavaScript")
    locale = json.loads(get("/locales/en/translation.json"))
    require(isinstance(locale, dict) and isinstance(locale.get("navbar"), dict) and bool(locale["navbar"].get("projects")), "Frontend English locale is missing")
    paths = json.loads(get("/openapi.json"))["paths"]
    require(all(method in paths.get(path, {}) for path, method in OPENAPI_OPERATIONS.items()), "Expected OpenAPI routes are missing")
    docs_scripts()
    print("Smoke passed: trusted local TLS, database health, per-request frontend CSP nonce, frontend entry/locale, all API families and the /docs CSP; no user mutations.")
