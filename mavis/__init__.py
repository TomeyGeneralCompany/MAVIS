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


    # Check individual comments so ordinary edits to these modules remain possible.
    for filename, expected in (
        ('media_research.py', '998ff6ec04582f457aced7a4765b9d7f66bb0959256d4c7a5eaf17d818e158bf'),
        ('local_voice.py', 'ed1042036bc3efac8b3803602f78dd35190006d51c82fe566b1243fe98b058e4'),
        ('shorts.py', '145ea8608c704174f2dda1b1215fdc86584ae3778202887774c571675428fb03'),
    ):
        try:
            lines = Path(__file__).with_name(filename).read_bytes().splitlines()
        except OSError:
            raise SystemExit(f'MAVIS startup refused: {filename} is missing or unreadable.') from None
        if sum(sha256(line).hexdigest() == expected for line in lines if line.startswith(b'# ')) != 1:
            raise SystemExit(f'MAVIS startup refused: embedded scripture in {filename} is missing or changed.')


_verify_scripture()
