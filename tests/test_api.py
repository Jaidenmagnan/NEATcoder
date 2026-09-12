import hashlib
import hmac

from neatcoder.api import _verify_signature


def test_verifies_github_signature() -> None:
    payload = b'{"ok": true}'
    signature = "sha256=" + hmac.new(b"secret", payload, hashlib.sha256).hexdigest()
    assert _verify_signature(payload, signature, "secret")
    assert not _verify_signature(payload, signature, "wrong")
