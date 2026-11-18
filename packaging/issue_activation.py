"""Publisher-side offline activation. Keep the private key outside GitHub."""
import argparse
import base64
import json
from pathlib import Path
import re
import uuid
from cryptography.hazmat.primitives.serialization import load_pem_private_key

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--private-key", type=Path, required=True)
    parser.add_argument("--device", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not re.fullmatch(r"[a-f0-9]{64}", args.device):
        parser.error("Device code must be the 64-character code shown in MAVIS.")
    if args.output.exists():
        parser.error("Refusing to replace an existing activation.")
    private = load_pem_private_key(args.private_key.read_bytes(), password=None)
    payload = {"version": 1, "device": args.device, "license_id": str(uuid.uuid4())}
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    license = {"payload": payload, "signature": base64.b64encode(private.sign(canonical)).decode("ascii")}
    args.output.write_text(json.dumps(license, indent=2) + "\n", encoding="utf-8")
    args.output.chmod(0o600)
    print("Issued one-machine activation:", args.output)

if __name__ == "__main__":
    main()
