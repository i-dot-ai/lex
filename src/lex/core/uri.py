"""Canonical URI normalisation for legislation.gov.uk identifiers."""

import re

CANONICAL_BASE = "http://www.legislation.gov.uk/id/"


def normalise_legislation_uri(uri: str) -> str:
    """Normalise any legislation URI variant to canonical http://.../id/... format.

    Handles: https->http, missing /id/ segment, /enacted suffix, short-form IDs.

    Examples:
        "ukpga/2023/52" -> "http://www.legislation.gov.uk/id/ukpga/2023/52"
        "https://www.legislation.gov.uk/id/ukpga/2023/52" -> "http://www.legislation.gov.uk/id/ukpga/2023/52"
        "http://www.legislation.gov.uk/ukpga/2023/52/enacted" -> "http://www.legislation.gov.uk/id/ukpga/2023/52"
    """
    if not uri:
        return uri

    uri = uri.strip()

    # Short form (e.g. "ukpga/2023/52") -- prepend canonical base
    if not uri.startswith("http"):
        return f"{CANONICAL_BASE}{uri.lstrip('/')}"

    # https -> http
    if uri.startswith("https://"):
        uri = "http://" + uri[8:]

    # Insert /id/ if missing (dc:identifier format)
    # e.g. http://www.legislation.gov.uk/ukpga/2023/52 -> .../id/ukpga/2023/52
    if uri.startswith("http://www.legislation.gov.uk/") and "/id/" not in uri:
        uri = uri.replace("http://www.legislation.gov.uk/", CANONICAL_BASE, 1)

    # Strip version suffixes (/enacted, /made, /created)
    uri = re.sub(r"/(enacted|made|created)(/.*)?$", "", uri)

    return uri
