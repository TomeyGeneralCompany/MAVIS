"""Offline packaging checks. No external downloads or root access required."""
import ast
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class PackagingTests(unittest.TestCase):
    def test_provision_script_compiles(self):
        ast.parse((ROOT / "packaging/provision.py").read_text())

    def test_installer_provisions_runtimes(self):
        script = (ROOT / "packaging/provision.py").read_text()
        for marker in ("ollama", "qwen3:4b", "qwen-tts", "sha256", "model-files.json"):
            self.assertIn(marker, script)

    def test_billing_disabled_in_debian_build(self):
        source = (ROOT / "packaging/deb.py").read_text()
        self.assertIn("'required': False", source)
        self.assertNotIn("--billing-url", source)

    def test_postinst_installs_runtimes(self):
        self.assertIn("packaging/provision.py", (ROOT / "packaging/postinst").read_text())


if __name__ == "__main__":
    unittest.main()
