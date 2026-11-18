"""Offline cryptographic, tampering and machine binding tests."""
import base64
import json
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding,PublicFormat
from mavis.activation import ActivationRequired, verify_license, payload_bytes, install_activation, require_activation

class ActivationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.private=Ed25519PrivateKey.generate()
        self.pub=self.root/"pub.pem"
        self.pub.write_bytes(self.private.public_key().public_bytes(Encoding.PEM,PublicFormat.SubjectPublicKeyInfo))
        self.device="a"*64
        self.payload={"version":1,"device":self.device,"license_id":"test-license"}
        self.license={"payload":self.payload,"signature":base64.b64encode(self.private.sign(payload_bytes(self.payload))).decode()}

    def test_valid_signature_machine_bound(self):
        self.assertEqual(verify_license(self.license,self.device,self.pub),self.payload)
        with self.assertRaisesRegex(ActivationRequired,"different computer"):
            verify_license(self.license,"b"*64,self.pub)

    def test_copy_and_tampering_fail(self):
        forged=json.loads(json.dumps(self.license))
        forged["payload"]["device"]="b"*64
        with self.assertRaises(ActivationRequired):
            verify_license(forged,"b"*64,self.pub)
        forged=json.loads(json.dumps(self.license))
        forged["signature"]="!!!"
        with self.assertRaises(ActivationRequired):
            verify_license(forged,self.device,self.pub)

    def test_install_and_restart(self):
        with patch("mavis.activation.PUBLIC_KEY",self.pub),patch("mavis.activation.machine_code",return_value=self.device):
            with self.assertRaises(ActivationRequired):
                require_activation(self.root)
            install_activation(self.root,self.license)
            self.assertEqual(require_activation(self.root),self.payload)
            self.assertEqual((self.root/"activation.json").stat().st_mode & 0o777,0o600)
