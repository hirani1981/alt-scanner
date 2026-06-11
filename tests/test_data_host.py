"""Host-fallback tests for the geo-block (HTTP 451) scenario.

GitHub Actions runners get 451 from api.binance.com. These tests mimic that
deterministically by mocking httpx so the first host returns 451 — the client
must advance to the next host rather than fail.

Run with:  python -m unittest tests.test_data_host -v
"""
import os
import unittest
from unittest import mock
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import data.binance as binance


class TestHostFallback(unittest.TestCase):
    def test_default_host_is_the_non_geoblocked_mirror(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertEqual(binance._hosts()[0], "https://data-api.binance.vision")

    def test_env_override_parses_comma_list(self):
        with mock.patch.dict(os.environ, {"BINANCE_API_BASE": "https://a.test/, https://b.test"}):
            self.assertEqual(binance._hosts(), ["https://a.test", "https://b.test"])

    def test_451_falls_through_to_next_host(self):
        calls = []

        def fake_get(url, params=None, timeout=None):
            calls.append(url)
            req = httpx.Request("GET", url)
            if "blocked.test" in url:
                return httpx.Response(451, request=req, text="Unavailable For Legal Reasons")
            return httpx.Response(200, request=req, json={"ok": True})

        with mock.patch.dict(os.environ, {"BINANCE_API_BASE": "https://blocked.test,https://good.test"}):
            with mock.patch.object(binance.httpx, "get", fake_get):
                out = binance._get("/api/v3/exchangeInfo")

        self.assertEqual(out, {"ok": True})
        self.assertTrue(any("blocked.test" in u for u in calls), "must try the blocked host first")
        self.assertTrue(any("good.test" in u for u in calls), "must fall through to the next host")

    def test_451_does_not_retry_the_same_host(self):
        """A geo-block is permanent for the runner — don't waste retries on it."""
        calls = []

        def fake_get(url, params=None, timeout=None):
            calls.append(url)
            req = httpx.Request("GET", url)
            if "blocked.test" in url:
                return httpx.Response(451, request=req, text="blocked")
            return httpx.Response(200, request=req, json={"ok": True})

        with mock.patch.dict(os.environ, {"BINANCE_API_BASE": "https://blocked.test,https://good.test"}):
            with mock.patch.object(binance.httpx, "get", fake_get):
                binance._get("/api/v3/klines")

        blocked_calls = [u for u in calls if "blocked.test" in u]
        self.assertEqual(len(blocked_calls), 1, "451 host must be hit exactly once, no retries")

    def test_all_hosts_blocked_raises_451(self):
        """If every host 451s (primary mirror also blocked), surface it loudly —
        that is the signal to add a cross-exchange fallback (Bybit/OKX)."""
        def fake_get(url, params=None, timeout=None):
            req = httpx.Request("GET", url)
            return httpx.Response(451, request=req, text="blocked")

        with mock.patch.dict(os.environ, {"BINANCE_API_BASE": "https://a.test,https://b.test"}):
            with mock.patch.object(binance.httpx, "get", fake_get):
                with self.assertRaises(httpx.HTTPStatusError) as ctx:
                    binance._get("/api/v3/ticker/24hr")
        self.assertEqual(ctx.exception.response.status_code, 451)


if __name__ == "__main__":
    unittest.main()
