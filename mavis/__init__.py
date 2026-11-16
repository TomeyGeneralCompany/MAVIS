"""MAVIS startup integrity check."""
from hashlib import sha256
from pathlib import Path


def _verify_scripture():
    expected = "9dde6c9daf19289a1c44e33397f53462096da9cea4630ead59ddbba407c3e0f1"
    try:
        # Read the source itself so cached bytecode cannot hide a missing verse.
        source = Path(__file__).with_name('scripture.py').read_bytes().replace(b'\r\n', b'\n')
    except OSError:
        raise SystemExit('MAVIS startup refused: embedded scripture is missing or unreadable.') from None
    if sha256(source).hexdigest() != expected:
        raise SystemExit('MAVIS startup refused: embedded scripture has been changed.')


_verify_scripture()
