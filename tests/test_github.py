"""GitHub client: pagination, error handling, rate limits — with a fake transport."""
import unittest
import urllib.error

from src import github as gh


def make_response(status=200, body=b"{}", headers=None):
    return status, headers or {}, body


class FakeTransport:
    def __init__(self, routes):
        # routes: list of (url_suffix, status, headers, body) OR exceptions
        self.routes = routes
        self.calls = []

    def __call__(self, url, headers):
        self.calls.append((url, headers))
        for route in self.routes:
            suffix, status, hdrs, body = route[:4]
            if isinstance(body, Exception):
                if suffix in url:
                    raise body
                continue
            if suffix in url:
                if isinstance(body, str):
                    body = body.encode()
                return status, hdrs, body
        raise AssertionError(f"unexpected url: {url}")


class Pagination(unittest.TestCase):
    def test_follows_rel_next(self):
        tx = FakeTransport([
            ("page=2", 200, {}, '[{"name": "r2"}]'),
            ("/users/x/repos?", 200, {"Link": '<https://api.github.com/users/x/repos?page=2>; rel="next", <...page=1>; rel="first"'}, "[]"),
        ])
        c = gh.Client(token="t", transport=tx)
        repos = c.repos("x")
        self.assertEqual(len(repos), 1)
        self.assertEqual(repos[0]["name"], "r2")
        self.assertEqual(len(tx.calls), 2)

    def test_no_next_link(self):
        tx = FakeTransport([("/users/x/repos?", 200, {}, "[]")])
        c = gh.Client(token="t", transport=tx)
        self.assertEqual(c.repos("x"), [])

    def test_max_pages_guard(self):
        link = {"Link": '<https://api.github.com/users/x/repos?page=2>; rel="next"'}
        tx = FakeTransport([("/users/x/repos?", 200, link, "[]"), ("page=2", 200, link, "[]")])
        c = gh.Client(token="t", transport=tx)
        c.repos("x")  # must not loop forever
        # MAX_PAGES applies to any paginated call
        self.assertLessEqual(len(tx.calls), gh.MAX_PAGES)


class ErrorHandling(unittest.TestCase):
    def test_401_raises(self):
        tx = FakeTransport([("/users/x", 401, {}, b'{"message": "bad credentials"}')])
        c = gh.Client(token="bad", transport=tx)
        with self.assertRaises(gh.GitHubError):
            c.user("x")

    def test_404_raises(self):
        tx = FakeTransport([("/users/x", 404, {}, b"{}")])
        c = gh.Client(token="t", transport=tx)
        with self.assertRaises(gh.GitHubError):
            c.user("x")

    def test_rate_limit_raises_without_retry(self):
        tx = FakeTransport([("/users/x", 403, {"X-RateLimit-Remaining": "0"}, b"{}")])
        c = gh.Client(token="t", transport=tx, retries=2, retry_delay=0)
        with self.assertRaises(gh.RateLimited):
            c.user("x")
        self.assertEqual(len(tx.calls), 1)  # no pointless retries

    def test_500_retries_then_fails(self):
        tx = FakeTransport([("/users/x", 500, {}, b"boom")])
        c = gh.Client(token="t", transport=tx, retries=2, retry_delay=0)
        with self.assertRaises(gh.GitHubError):
            c.user("x")
        self.assertEqual(len(tx.calls), 3)  # 1 + 2 retries

    def test_malformed_json_raises(self):
        tx = FakeTransport([("/users/x", 200, {}, b"not json at all")])
        c = gh.Client(token="t", transport=tx)
        with self.assertRaises(gh.GitHubError):
            c.user("x")

    def test_network_failure_retries_then_raises(self):
        tx = FakeTransport([("/users/x", 0, {}, urllib.error.URLError("no route"))])
        c = gh.Client(token="t", transport=tx, retries=1, retry_delay=0)
        with self.assertRaises(gh.GitHubError):
            c.user("x")
        self.assertEqual(len(tx.calls), 2)


class AuthHeader(unittest.TestCase):
    def test_token_sent(self):
        tx = FakeTransport([("/users/x", 200, {}, b"{}")])
        c = gh.Client(token="secret", transport=tx)
        c.user("x")
        self.assertEqual(tx.calls[0][1]["Authorization"], "Bearer secret")

    def test_no_token_anonymous(self):
        import os

        old = os.environ.pop("GITHUB_TOKEN", None)
        try:
            tx = FakeTransport([("/users/x", 200, {}, b"{}")])
            c = gh.Client(transport=tx)
            c.user("x")
            self.assertNotIn("Authorization", tx.calls[0][1])
        finally:
            if old:
                os.environ["GITHUB_TOKEN"] = old


class NextLink(unittest.TestCase):
    def test_parsing(self):
        self.assertEqual(
            gh._next_link('<https://a?page=2>; rel="next", <https://a?page=1>; rel="first"'),
            "https://a?page=2",
        )
        self.assertIsNone(gh._next_link(""))
        self.assertIsNone(gh._next_link('<https://a?page=1>; rel="first"'))
        self.assertEqual(
            gh._next_link("<https://a?page=3>; rel=next"),
            "https://a?page=3",
        )


if __name__ == "__main__":
    unittest.main()
