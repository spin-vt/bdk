"""Small input validators shared by the API routes."""

import re

# Deliberately simple: something@something.tld, no whitespace. Real validation
# happens via the verification email; this only rejects obvious garbage before
# it lands in the database.
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def is_valid_email(value):
    return isinstance(value, str) and len(value) <= 254 and bool(_EMAIL_RE.match(value))
