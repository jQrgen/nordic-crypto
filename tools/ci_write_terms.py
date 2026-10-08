#!/usr/bin/env python3
"""Write state/private_terms.json from the NC_PRIVATE_TERMS_JSON environment variable.

The privacy gate reads that file and fails closed when it is missing. The value is
the box-only term list. This script prints how many rules it wrote and nothing else:
not the text, not a JSON error snippet, not a bad pattern.
"""
import json
import os
import re
import stat
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEST = os.path.join(ROOT, "state", "private_terms.json")


class TermsError(Exception):
    """A problem we can report without quoting the secret."""


def validate(raw):
    """Return the term object, or raise TermsError. The message names no rule text."""
    if raw is None or not str(raw).strip():
        raise TermsError(
            "NC_PRIVATE_TERMS_JSON is empty. On the box, run: "
            "gh secret set NC_PRIVATE_TERMS_JSON < state/private_terms.json"
        )
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        raise TermsError("NC_PRIVATE_TERMS_JSON is not valid JSON.") from None
    if not isinstance(data, dict) or not data:
        raise TermsError("NC_PRIVATE_TERMS_JSON must be a non-empty JSON object.")
    for key, value in data.items():
        if not isinstance(key, str) or not key or not isinstance(value, str) or not value:
            raise TermsError("NC_PRIVATE_TERMS_JSON entries must be non-empty strings.")
        try:
            re.compile(value, re.I)
        except re.error:
            raise TermsError(
                "NC_PRIVATE_TERMS_JSON has a rule that is not a valid regular expression."
            ) from None
    return data


def write_terms(raw, path):
    """Validate `raw` and write it to `path` (mode 0600). Return the rule count."""
    data = validate(raw)
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    tmp = path + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=1)
            fh.write("\n")
            fh.flush()
            os.fsync(fh.fileno())
        os.chmod(tmp, stat.S_IRUSR | stat.S_IWUSR)
        os.replace(tmp, path)
    except Exception:
        try:
            os.remove(tmp)
        except OSError:
            pass
        raise
    return len(data)


def main():
    try:
        n = write_terms(os.environ.get("NC_PRIVATE_TERMS_JSON", ""), DEST)
    except TermsError as ex:
        print(f"::error::{ex}", file=sys.stderr)
        return 1
    print(f"wrote state/private_terms.json ({n} rules)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
