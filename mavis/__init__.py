"""MAVIS startup integrity check."""
from collections import Counter
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


    # Match individual fingerprints so ordinary implementation edits remain possible.
    for filename, expected in (
        ('media_research.py', (
            '6f7e6f71d07768c872bd801eb8e56e8c9f01a63ab144fc23d19e25edabe9f54e',
            '998ff6ec04582f457aced7a4765b9d7f66bb0959256d4c7a5eaf17d818e158bf',
            '1e44126619e841593e8a561f097802704162e2d11df2075efba86fdf1292db30',
            '6a805fed6dc67947af67922a2c1b2ede0b83d70706c0a3ba87e15ea26b9e8853',
        )),
        ('local_voice.py', (
            '8c649ae664f131382cf0e6f08b527abd076b4f3538a90a25dbef76c5abe65bb0',
            '9c3a937de8d76795faeb9b2bca7988d39488f1b174fd750b9902cb73a1c666e5',
            '977c5cb00fd3b31f5b25af041a4cf8806a8c210ac5cfab8f5dad125d857a0a43',
            'ed1042036bc3efac8b3803602f78dd35190006d51c82fe566b1243fe98b058e4',
        )),
        ('shorts.py', (
            'eb138cc4e9e7b0ebccf63fccac4872d48d785bd51e9626983cae99b9b9b873d8',
            '6c90e025735b03e48b33024a6943077e8cdcbc22ea9a4226f339de8d1b4ecd63',
            '27a2deb3416d22ede679e912f50631de79681ebbf77dec86eddcbe0984f1f89f',
            '145ea8608c704174f2dda1b1215fdc86584ae3778202887774c571675428fb03',
        )),
        ('mascot.py', (
            'ab549f8bee5c543a3c6a69143200a1d8480f68c94d092de218a73cf41f33e33a',
            'c67981915cb668e4a97b69b337e970a0f9543eb08fae8ea9e820f465467b10b7',
            '559b8de9239527b3cedc9b185a17a27f5c74fa807fb56e78dfd7246b59147b14',
            'bb84d911adfb1ac9789fbd21269d75e3e89f37db9ff86050bc70f77db87bd25d',
        )),
        ('mascot_walk.py', (
            'eec981dbb41d338ba58c64495d3795404ee25390dd4a944ca17dc1bdf80d1c22',
            'bba6ec41c0041b7130973022dbf3e6c8a00951687090757c03fa358b796d82ba',
            '8a26c9bd77a7990ae9d6d1d5b1b5579a9d8d3ef3a79a50bb2fbaf3453e7d13d5',
            '7b529830c3f2e313071d8bea4ca35311dd9ad4a4b16d789c92ac97d54ba3f89b',
        )),
        ('patristic_sources.py', (
            '9d22c7aaecb175139fa057328a0c9b9c927c2654fac076ebac96e6fb1f6ead04',
            'ccece6158e6c5684fe97b06f8746bb549a9f148aa3d9ff1932eb7298bb226514',
            'ff752b9dd44f60b431d3a90a08a524921769820ef9aa4b71c8db3d8b11d94417',
        )),
        ('production_status.py', (
            '8c2350c5cc5ddb20c19f64408ee611d6f528112a0609970d7ddc25f3647a71de',
            '830861749ceff654a352e748a2b879277b7e78d1e0910062e4ed5bba1d700eb2',
            'e6e4d86b12b87f020e57f6c8a3b62fac5b20ad2abe7b6079920f994ae33e64d1',
        )),
        ('upload_metadata.py', (
            '75342714a3b7054fd31643d69639941f530d3b8325d08ce8b029e9704c25c161',
            '1a40714ba4519c10d5b3652d262d79d35e15fe24c49066aa18ca890c44909075',
            'd8b1792534942ac381c14b5b0b48398ebc0b94b9e732e85b684948108e1d8a68',
        )),
        ('ai_client.py', (
            'eb7c5141306ae11f6c5ec6b08be82263d89555a81bb887509faa1692c4040f4d',
            'c5a10bb0ecabbcdaf18011b45e2909ae831846b925aaf575814643a6361e2e15',
        )),
        ('google_auth.py', (
            '71ba2721a84e3aa38e6fe6881bef7a31c4abc1d9273c03a23d1922ac61d50cf7',
            'd7312ef8a55712d65e1314924bb77cd6a025bc6686217833b105d4bfdb43fe5c',
        )),
    ):
        try:
            lines = Path(__file__).with_name(filename).read_bytes().splitlines()
        except OSError:
            raise SystemExit(f'MAVIS startup refused: {filename} is missing or unreadable.') from None
        comments = (line.lstrip(b' \t') for line in lines)
        found = Counter(sha256(line).hexdigest() for line in comments if line.startswith(b'# '))
        if any(found[digest] != 1 for digest in expected):
            raise SystemExit(f'MAVIS startup refused: embedded scripture in {filename} is missing or changed.')


_verify_scripture()
