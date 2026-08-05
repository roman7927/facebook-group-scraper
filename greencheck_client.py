"""Signed HTTP client for the Green Check scraper API; never handles Facebook credentials."""
import base64
import hashlib
import hmac
import json
import os
import secrets
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class GreenCheckError(RuntimeError):
    def __init__(self, status, message, temporary=False, uncertain=False):
        super().__init__(message)
        self.status, self.temporary, self.uncertain = status, temporary, uncertain


def utc_now():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def sign(secret, timestamp, nonce, method, path, body):
    body_hash = hashlib.sha256(body).hexdigest()
    canonical = "\n".join((timestamp, nonce, method.upper(), path, body_hash))
    return hmac.new(secret.encode(), canonical.encode(), hashlib.sha256).hexdigest()


class GreenCheckClient:
    def __init__(self, base_url=None, client_id=None, secret=None, schema_version=None, timeout=None):
        self.base_url = (base_url or os.getenv("GREENCHECK_API_BASE_URL", "")).rstrip("/")
        self.client_id = client_id or os.getenv("GREENCHECK_API_CLIENT_ID", "roman-home-facebook-scraper")
        self.secret = secret or os.getenv("GREENCHECK_API_SECRET", "")
        self.schema_version = schema_version or os.getenv("GREENCHECK_API_SCHEMA_VERSION", "1.0")
        self.timeout = int(timeout or os.getenv("GREENCHECK_API_TIMEOUT_SECONDS", "30"))
        if not self.base_url or not self.secret:
            raise ValueError("Green Check requires GREENCHECK_API_BASE_URL and GREENCHECK_API_SECRET")

    def request(self, method, path, payload=None):
        body = b"" if payload is None else json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        timestamp, nonce = utc_now(), secrets.token_urlsafe(24)
        headers = {"Content-Type": "application/json", "X-GreenCheck-Client": self.client_id, "X-GreenCheck-Timestamp": timestamp, "X-GreenCheck-Nonce": nonce, "X-GreenCheck-Schema-Version": self.schema_version, "X-GreenCheck-Signature": sign(self.secret, timestamp, nonce, method, path, body)}
        request = Request(self.base_url + path, data=body if method != "GET" else None, headers=headers, method=method)
        try:
            with urlopen(request, timeout=self.timeout) as response:
                return response.status, json.loads(response.read().decode("utf-8") or "{}")
        except HTTPError as error:
            status = error.code
            temporary = status == 429 or status >= 500
            detail = error.read().decode("utf-8", "replace")[:1000]
            raise GreenCheckError(status, f"Green Check HTTP {status}: {detail}", temporary, temporary) from error
        except (URLError, TimeoutError) as error:
            raise GreenCheckError(None, "Green Check network failure", True, True) from error

    def config(self): return self.request("GET", "/api/v1/scraper/config")[1]
    def state(self): return self.request("GET", "/api/v1/scraper/state")[1]
    def ingest(self, payload): return self.request("POST", "/api/v1/scraper/ingest", payload)[1]
    def heartbeat(self, payload): return self.request("POST", "/api/v1/scraper/heartbeat", payload)[1]
    def batch(self, batch_id): return self.request("GET", f"/api/v1/scraper/batches/{batch_id}")[1]
