"""Offline device-bound licenses verified with the publisher's Ed25519 public key."""
import base64
import hashlib
import json
import os
from pathlib import Path
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.serialization import load_pem_public_key

PUBLIC_KEY = Path(__file__).with_name("activation-public.pem")
MACHINE_ID = Path("/etc/machine-id")

class ActivationRequired(PermissionError):
    pass

def machine_code(machine_file=MACHINE_ID):
    try:
        value = Path(machine_file).read_text(encoding="ascii").strip().lower()
    except OSError as exc:
        raise ActivationRequired("Machine identifier unavailable.") from exc
    if len(value) != 32 or any(c not in "0123456789abcdef" for c in value):
        raise ActivationRequired("Machine identifier is invalid.")
    return hashlib.sha256(("mavis-device-v1:" + value).encode()).hexdigest()

def payload_bytes(payload):
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()

def verify_license(data, device=None, public_key=None):
    try:
        if not isinstance(data, dict) or set(data) != {"payload", "signature"}:
            raise ValueError("Invalid license envelope.")
        payload = data["payload"]
        if (not isinstance(payload, dict) or set(payload) != {"version", "device", "license_id"}
            or type(payload["version"]) is not int or payload["version"] != 1
            or not isinstance(payload["device"], str) or not isinstance(payload["license_id"], str)
            or not payload["license_id"]):
            raise ValueError("Invalid license payload.")
        signature = base64.b64decode(data["signature"], validate=True)
        key = load_pem_public_key(Path(public_key or PUBLIC_KEY).read_bytes())
        key.verify(signature, payload_bytes(payload))
        if payload["device"] != (device if device is not None else machine_code()):
            raise ActivationRequired("This license belongs to a different computer.")
    except (ValueError, TypeError, KeyError, InvalidSignature, OSError) as exc:
        raise ActivationRequired("Invalid publisher signature or activation format.") from exc
    return payload

def license_path(root):
    return Path(root) / "activation.json"

def require_activation(root):
    try:
        data = json.loads(license_path(root).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ActivationRequired("MAVIS requires activation for this computer.") from exc
    return verify_license(data)

def install_activation(root, data):
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except ValueError as exc:
            raise ActivationRequired("Activation must contain valid JSON.") from exc
    verify_license(data)
    path = license_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(".activation.tmp")
    try:
        with temp.open("w", encoding="utf-8") as file:
            os.chmod(temp, 0o600)
            json.dump(data, file, sort_keys=True)
        temp.replace(path)
    finally:
        temp.unlink(missing_ok=True)
