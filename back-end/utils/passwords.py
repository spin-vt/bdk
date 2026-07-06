"""Non-throwing password verification for every login door.

werkzeug 3.x removed the legacy salted hash methods (bare ``sha256``/``md5``),
so ``check_password_hash`` raises ValueError on hashes written by the old
stack (``sha256$<salt>$<hexdigest>``) instead of returning False — which
turned every legacy-account login into a 500. Route all login checks through
``verify_password``: it verifies legacy hashes with the stdlib primitive the
old werkzeug used, and treats any malformed/None hash as bad credentials,
never a server error. Pair with ``needs_rehash`` to transparently upgrade an
account to pbkdf2 on its next successful login.
"""

import hashlib
import hmac

from werkzeug.security import check_password_hash

# What new/migrated hashes are written with (user_ops uses the same scheme).
PREFERRED_METHOD = "pbkdf2:sha256"


def _verify_legacy_sha256(stored, password):
    # Old werkzeug's salted simple hash for method='sha256':
    #   digest = HMAC(key=salt, msg=password, sha256).hexdigest()
    # (validated against werkzeug 2.2.3, the version that wrote these hashes).
    method, salt, digest = stored.split("$", 2)
    if method != "sha256" or not salt or not digest:
        return False
    calc = hmac.new(salt.encode("utf-8"), password.encode("utf-8"), hashlib.sha256).hexdigest()
    return hmac.compare_digest(calc, digest)


def verify_password(stored, password):
    """True iff ``password`` matches the ``stored`` hash. Handles current
    pbkdf2 hashes and legacy bare-sha256 hashes; returns False (rather than
    raising) for None/empty/malformed hashes and non-string passwords."""
    if not stored or not isinstance(password, str):
        return False
    if stored.startswith("sha256$") and stored.count("$") == 2:
        return _verify_legacy_sha256(stored, password)
    try:
        return check_password_hash(stored, password)
    except (ValueError, TypeError):
        # Unknown/removed method or malformed hash: bad credentials, not a 500.
        return False


def needs_rehash(stored):
    """True when a successfully-verified hash should be rewritten with
    ``PREFERRED_METHOD`` (i.e. it still uses a legacy scheme)."""
    return bool(stored) and not stored.startswith("pbkdf2:")
