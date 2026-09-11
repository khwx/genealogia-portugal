"""Unit tests for the shared Supabase pagination helper `fetch_paginated`.

These verify the fix for the pagination bug (Supabase caps queries at 1000
rows): the helper must walk every page and merge results instead of reading
only the first batch. No network is touched — `urllib.request.urlopen` is
monkeypatched.
"""

import json
import sys
import unittest
from unittest.mock import patch, MagicMock

# Make the repo root importable when run directly from scripts/ or repo root.
sys.path.insert(0, ".")

import sync_htr_supabase as s


class _FakeResp:
    """Context-manager response returning a JSON-encoded list of rows."""

    def __init__(self, rows):
        self._rows = rows

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def read(self):
        return json.dumps(self._rows).encode("utf-8")


def _rows(n, start=0):
    return [{"file_id": f"f{start + i}"} for i in range(n)]


class TestFetchPaginated(unittest.TestCase):

    def test_merges_multiple_pages(self):
        # 1000 + 500 -> must return all 1500, not just the first batch.
        pages = [_rows(1000), _rows(500, 1000)]

        def fake_urlopen(req, timeout=30):
            return _FakeResp(pages.pop(0))

        with patch("urllib.request.urlopen", side_effect=fake_urlopen):
            rows = s.fetch_paginated("file_id")
        self.assertEqual(len(rows), 1500)
        self.assertEqual(rows[0]["file_id"], "f0")
        self.assertEqual(rows[1499]["file_id"], "f1499")

    def test_stops_when_page_smaller_than_cap(self):
        pages = [_rows(1000), _rows(300, 1000)]

        def fake_urlopen(req, timeout=30):
            return _FakeResp(pages.pop(0))

        with patch("urllib.request.urlopen", side_effect=fake_urlopen):
            rows = s.fetch_paginated("file_id")
        self.assertEqual(len(rows), 1300)

    def test_single_small_page(self):
        with patch("urllib.request.urlopen", return_value=_FakeResp(_rows(42))):
            rows = s.fetch_paginated("file_id")
        self.assertEqual(len(rows), 42)

    def test_empty_result(self):
        with patch("urllib.request.urlopen", return_value=_FakeResp([])):
            rows = s.fetch_paginated("file_id")
        self.assertEqual(rows, [])

    def test_handles_network_error_gracefully(self):
        # A failure mid-stream should return what was already collected.
        calls = {"n": 0}

        def fake_urlopen(req, timeout=30):
            calls["n"] += 1
            if calls["n"] == 1:
                return _FakeResp(_rows(1000))
            raise OSError("boom")

        with patch("urllib.request.urlopen", side_effect=fake_urlopen):
            rows = s.fetch_paginated("file_id")
        self.assertEqual(len(rows), 1000)

    def test_get_synced_file_ids_uses_pagination(self):
        pages = [_rows(1000), _rows(2, 1000)]

        def fake_urlopen(req, timeout=30):
            return _FakeResp(pages.pop(0))

        with patch("urllib.request.urlopen", side_effect=fake_urlopen):
            ids = s.get_synced_file_ids()
        self.assertEqual(len(ids), 1002)
        self.assertIn("f0", ids)
        self.assertIn("f1001", ids)


if __name__ == "__main__":
    unittest.main(verbosity=2)
