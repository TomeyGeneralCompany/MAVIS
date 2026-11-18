"""Live localhost flow: unactivated dashboard, license submission, and job gate."""
import base64
import json
from pathlib import Path
import re
import tempfile
import threading
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from mavis.activation import payload_bytes
from local_studio import Studio, serve


class ActivationHttpTests(unittest.TestCase):
    def test_browser_requires_signed_machine_activation(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            private = Ed25519PrivateKey.generate()
            public = root / "publisher.pem"
            public.write_bytes(private.public_key().public_bytes(Encoding.PEM, PublicFormat.SubjectPublicKeyInfo))
            device = "f" * 64
            payload = {"version": 1, "device": device, "license_id": "issued-to-one-device"}
            license = {"payload": payload,
                       "signature": base64.b64encode(private.sign(payload_bytes(payload))).decode()}
            with patch("mavis.activation.PUBLIC_KEY", public), \
                 patch("mavis.activation.machine_code", return_value=device), \
                 patch("local_studio.machine_code", return_value=device):
                with serve(Studio(root), 0) as server:
                    thread = threading.Thread(target=server.serve_forever, daemon=True)
                    thread.start()
                    url = "http://127.0.0.1:" + str(server.server_port)
                    try:
                        with urlopen(url + "/") as response:
                            page = response.read().decode()
                        self.assertIn("Activate this computer", page)
                        self.assertIn(device, page)
                        token = re.search(r"const token='([^']+)'", page).group(1)
                        with self.assertRaises(HTTPError) as blocked:
                            urlopen(url + "/overview")
                        self.assertEqual(blocked.exception.code, 403)
                        req = Request(url + "/jobs", data=b"{}", headers={"X-Studio-Token": token})
                        with self.assertRaises(HTTPError) as blocked:
                            urlopen(req)
                        self.assertEqual(blocked.exception.code, 403)
                        req = Request(url + "/activation",
                                      data=json.dumps({"license": json.dumps(license)}).encode(),
                                      headers={"X-Studio-Token": token, "Content-Type": "application/json"})
                        with urlopen(req) as response:
                            self.assertTrue(json.load(response)["active"])
                        with urlopen(url + "/") as response:
                            page = response.read().decode()
                        self.assertIn("Media Automation and Video Integration System", page)
                        self.assertNotIn("Activate this computer", page)
                    finally:
                        server.shutdown()
                        thread.join()
