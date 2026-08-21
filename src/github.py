"""Minimal, dependency-free GitHub REST v3 client.

Design goals (from the profile spec):
- pagination via the Link header
- explicit failure modes: GitHubError / RateLimited — callers must fail the
  whole generation rather than render empty data
- auth via GITHUB_TOKEN when present; the built-in Actions token is enough,
  no PAT and no extra secrets are ever needed
"""
from __future__ import annotations

import json
import os
import time
import typing as t
import urllib.error
import urllib.request

API_ROOT = "https://api.github.com"
MAX_PAGES = 20
DEFAULT_RETRIES = 2
DEFAULT_RETRY_DELAY = 1.5

Transport = t.Callable[[str, dict], t.Tuple[int, dict, bytes]]
"""transport(url, headers) -> (status, headers, body). Raises on network failure."""


class GitHubError(RuntimeError):
    """Any failure talking to the GitHub API."""


class RateLimited(GitHubError):
    """Rate limit exhausted — do not retry, fail the generation."""


def _http_once(url: str, headers: dict) -> t.Tuple[int, dict, bytes]:
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, dict(resp.headers), resp.read()
    except urllib.error.HTTPError as exc:  # 4xx/5xx responses, not failures
        return exc.code, dict(exc.headers or {}), exc.read()


class Client:
    def __init__(
        self,
        token: t.Optional[str] = None,
        transport: t.Optional[Transport] = None,
        user_agent: str = "lairifangtang-hue-profile/1.0",
        retries: int = DEFAULT_RETRIES,
        retry_delay: float = DEFAULT_RETRY_DELAY,
    ) -> None:
        self.token = token if token is not None else (os.environ.get("GITHUB_TOKEN") or None)
        self.user_agent = user_agent
        self._raw = transport or _http_once
        self.retries = retries
        self.retry_delay = retry_delay

    # -- transport ----------------------------------------------------
    def _request(self, url: str) -> t.Tuple[int, dict, bytes]:
        """One logical request with retry on network errors and 5xx."""
        last_exc: Exception | None = None
        for attempt in range(self.retries + 1):
            try:
                status, headers, body = self._raw(url, self._headers())
            except (urllib.error.URLError, TimeoutError, OSError) as exc:
                last_exc = exc
                if attempt < self.retries:
                    time.sleep(self.retry_delay * (attempt + 1))
                    continue
                raise GitHubError(f"network failure contacting {url}: {last_exc}")
            if status >= 500 and attempt < self.retries:
                time.sleep(self.retry_delay * (attempt + 1))
                continue
            return status, headers, body
        raise GitHubError(f"request to {url} failed after retries")

    def _headers(self) -> dict:
        headers = {
            "User-Agent": self.user_agent,
            "Accept": "application/vnd.github+json",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    # -- requests -----------------------------------------------------
    def _check(self, url: str, status: int, headers: dict, body: bytes) -> None:
        if status in (403, 429):
            remaining = headers.get("X-RateLimit-Remaining", headers.get("x-ratelimit-remaining"))
            if remaining == "0" or status == 429:
                raise RateLimited(f"GitHub rate limit exceeded on {url}")
        if status == 401:
            raise GitHubError(f"authentication failed (401) on {url}")
        if status == 404:
            raise GitHubError(f"not found (404): {url}")
        if status >= 400:
            snippet = body[:200].decode("utf-8", "replace")
            raise GitHubError(f"HTTP {status} on {url}: {snippet}")

    def _get_json(self, url: str) -> t.Tuple[t.Any, dict]:
        status, headers, body = self._request(url)
        self._check(url, status, headers, body)
        try:
            return json.loads(body.decode("utf-8")), headers
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise GitHubError(f"malformed JSON from {url}: {exc}") from None

    def _paginate(self, path: str) -> list:
        items: list = []
        url: t.Optional[str] = API_ROOT + path
        pages = 0
        while url and pages < MAX_PAGES:
            data, headers = self._get_json(url)
            if not isinstance(data, list):
                raise GitHubError(f"expected a JSON list from {url}")
            items.extend(data)
            url = _next_link(headers.get("Link", ""))
            pages += 1
        return items

    # -- public API ---------------------------------------------------
    def user(self, login: str) -> dict:
        data, _ = self._get_json(f"{API_ROOT}/users/{login}")
        if not isinstance(data, dict):
            raise GitHubError(f"expected an object from /users/{login}")
        return data

    def repos(self, login: str) -> list:
        return self._paginate(f"/users/{login}/repos?per_page=100&sort=pushed")

    def languages(self, login: str, repo: str) -> dict:
        data, _ = self._get_json(f"{API_ROOT}/repos/{login}/{repo}/languages")
        if not isinstance(data, dict):
            raise GitHubError(f"expected an object from /repos/{login}/{repo}/languages")
        return data

    def events(self, login: str) -> list:
        return self._paginate(f"/users/{login}/events/public?per_page=100")


def _next_link(link_header: str) -> t.Optional[str]:
    """Extract the rel="next" URL from a Link header, if any."""
    if not link_header:
        return None
    for part in link_header.split(","):
        bits = part.split(";")
        if len(bits) < 2:
            continue
        url = bits[0].strip().strip("<>")
        if any('rel="next"' in b or "rel=next" in b for b in bits[1:]):
            return url
    return None
