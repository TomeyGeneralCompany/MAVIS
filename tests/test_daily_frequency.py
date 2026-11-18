"""Daily output frequency: defaults, bounds, persistence and real browser endpoint."""
from datetime import datetime, timezone
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from local_studio import Studio, serve
from run_mavis import config, slots


class DailyVideoCountTests(unittest.TestCase):
    def test_default_is_one_at_existing_anchor(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(config(Path(tmp))["videos_per_day"], 1)
            self.assertEqual(config(Path(tmp))["publish_times"], ["18:00"])

    def test_one_to_five_unique_publication_times(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for count in range(1, 6):
                (root / "mavis.json").write_text(json.dumps({
                    "videos_per_day": count, "mode": "scheduled", "publish_times": ["18:00"]
                }))
                cfg = config(root)
                self.assertEqual(len(cfg["publish_times"]), count)
                self.assertEqual(len(set(cfg["publish_times"])), count)
                self.assertIn("18:00", cfg["publish_times"])
                upcoming = slots(cfg, datetime(2026, 11, 18, 0, tzinfo=timezone.utc), upcoming=True)
                self.assertTrue(upcoming)

    def test_reject_invalid_counts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for count in (0, 6, -1, True, "3", 2.5):
                (root / "mavis.json").write_text(json.dumps({"videos_per_day": count}))
                with self.subTest(count=count), self.assertRaisesRegex(ValueError, "videos_per_day"):
                    config(root)

    def test_studio_persists_setting_and_rejects_out_of_range(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with patch("local_studio.require_activation", return_value={"license_id": "test"}):
                with serve(Studio(root), 0) as server:
                    thread = threading.Thread(target=server.serve_forever, daemon=True)
                    thread.start()
                    base = "http://127.0.0.1:" + str(server.server_port)
                    try:
                        with urlopen(base + "/") as response:
                            page = response.read().decode()
                        self.assertIn('id="videos-per-day"', page)
                        import re
                        token = re.search(r"'X-Studio-Token':'([^']+)'", page).group(1)
                        def submit(value, auth=token):
                            request = Request(
                                base + "/schedule",
                                data=json.dumps({"videos_per_day": value}).encode(),
                                headers={"X-Studio-Token": auth, "Content-Type": "application/json"}
                            )
                            with urlopen(request, timeout=5) as response:
                                return json.load(response)
                        with self.assertRaises(HTTPError) as error:
                            submit(2, auth="bad")
                        self.assertEqual(error.exception.code, 403)
                        self.assertEqual(submit(5)["videos_per_day"], 5)
                        self.assertEqual(config(root)["videos_per_day"], 5)
                        with urlopen(base + "/overview") as response:
                            self.assertEqual(json.load(response)["videos_per_day"], 5)
                        with self.assertRaises(HTTPError) as error:
                            submit(6)
                        self.assertEqual(error.exception.code, 400)
                        self.assertEqual(config(root)["videos_per_day"], 5)
                        self.assertEqual(submit(1)["videos_per_day"], 1)
                        self.assertEqual(config(root)["publish_times"], ["18:00"])
                    finally:
                        server.shutdown()
                        thread.join()
