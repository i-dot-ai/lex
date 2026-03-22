"""Regnal year parsing for pre-1963 UK legislation.

Before the Acts of Parliament Numbering and Citation Act 1962 (effective
1 January 1963), every Act of Parliament was dated by the regnal year of
the reigning monarch — the number of years since their accession.

The formula: year = monarch_accession_year + session_number - 1

Example: "5 & 6 Vict. c. 45" → Victoria acceded 1837, so 1837 + 5 - 1 = 1841.

This module is the single authoritative source for converting regnal year
references to calendar years. It handles:
  - Standard numeric URIs (post-1963)
  - Canonical regnal year URIs
  - Nonstandard separators from OCR damage (slashes, underscores, concatenation)
  - Freetext citations ("52 & 53 Vict. c. clviii")
  - Combined reign references ("Edw8and1Geo6")
  - Embedded years in Act names
  - Short title citations from section text content
"""

import re

# ── Monarch table ─────────────────────────────────────────────────────────
# Canonical abbreviation → (accession_year, end_year)
# 33 sovereigns from Henry III (1216) to Elizabeth II (2022).

REGNAL_YEAR_RANGES: dict[str, tuple[int, int]] = {
    "Hen3": (1216, 1272),
    "Edw1": (1272, 1307),
    "Edw2": (1307, 1327),
    "Edw3": (1327, 1377),
    "Ric2": (1377, 1399),
    "Hen4": (1399, 1413),
    "Hen5": (1413, 1422),
    "Hen6": (1422, 1461),
    "Edw4": (1461, 1483),
    "Edw5": (1483, 1483),  # Edward V — reigned April-June 1483
    "Ric3": (1483, 1485),
    "Hen7": (1485, 1509),
    "Hen8": (1509, 1547),
    "Edw6": (1547, 1553),
    "Mar1": (1553, 1558),  # Mary I / Philip & Mary
    "Eliz1": (1558, 1603),
    "Jas1": (1603, 1625),  # James I
    "Cha1": (1625, 1649),  # Charles I
    "Cha2": (1660, 1685),  # Charles II (backdated from 1649 by legal fiction)
    "Will3": (1689, 1702),  # William III / William & Mary
    "WillandMar": (1689, 1694),
    "Ann": (1702, 1714),
    "Geo1": (1714, 1727),
    "Geo2": (1727, 1760),
    "Geo3": (1760, 1820),
    "Geo4": (1820, 1830),
    "Will4": (1830, 1837),
    "Vict": (1837, 1901),
    "Edw7": (1901, 1910),
    "Edw8": (1936, 1936),  # Edward VIII — abdicated Dec 1936, only 1 session year
    "Geo5": (1910, 1936),
    "Geo6": (1936, 1952),
    "Eliz2": (1952, 2022),
}


# ── Monarch aliases ───────────────────────────────────────────────────────
# Lowercase variants → canonical key. None means ambiguous (needs number suffix).
# Covers: OCR damage, Latinised forms, Acts of English Parliament abbreviations,
# Romanised numerals, and common misspellings from digitised records.

MONARCH_ALIASES: dict[str, str | None] = {
    # Victoria (including Latinised form from OCR)
    "victoria": "Vict", "victoriae": "Vict", "vict": "Vict", "vic": "Vict",
    # George (need number to disambiguate)
    "george": None,
    "geo1": "Geo1", "geo2": "Geo2", "geo3": "Geo3",
    "geo4": "Geo4", "geo5": "Geo5", "geo6": "Geo6",
    # Edward (need number)
    "edward": None,
    "edw1": "Edw1", "edw2": "Edw2", "edw3": "Edw3",
    "edw4": "Edw4", "edw5": "Edw5", "edw6": "Edw6",
    "edw7": "Edw7", "edw8": "Edw8",
    "edwvii": "Edw7",  # Romanised form from OCR
    # Henry (need number)
    "henry": None,
    "hen3": "Hen3", "hen4": "Hen4", "hen5": "Hen5",
    "hen6": "Hen6", "hen7": "Hen7", "hen8": "Hen8",
    # William (need number)
    "william": None,
    "will3": "Will3", "will4": "Will4",
    # Charles
    "charles": None,
    "cha1": "Cha1", "chas1": "Cha1", "cha2": "Cha2", "chas2": "Cha2",
    # James (including short form from Acts of English Parliament URIs)
    "james": None,
    "jas1": "Jas1", "jas2": "Jas1",  # Jas2 not in table — map to Jas1 for safety
    "ja1": "Jas1", "ja2": "Jas1",  # aep/ paths use Ja1, Ja2
    # Anne
    "anne": "Ann", "ann": "Ann",
    # Richard
    "ric2": "Ric2", "ric3": "Ric2",  # Ric3 not in table
    "richard": None,
    # Elizabeth
    "eliz1": "Eliz1", "eliz": "Eliz1", "elizabeth": None, "eliz2": "Eliz2",
    # Mary / Philip & Mary
    "mary": "Mar1", "mar1": "Mar1",
    "willandmar": "WillandMar", "willandmarsess2": "WillandMar",
    "philandmar": "Mar1", "philandmarsess": "Mar1",
}

# Build fast lookup from canonical keys
for _key in REGNAL_YEAR_RANGES:
    _lower = _key.lower()
    if _lower not in MONARCH_ALIASES:
        MONARCH_ALIASES[_lower] = _key


# ── Compiled patterns ─────────────────────────────────────────────────────

_MONARCH_PATTERN = "|".join(
    re.escape(k) for k in sorted(REGNAL_YEAR_RANGES.keys(), key=len, reverse=True)
)
_REGNAL_RE = re.compile(rf"(?i)\b({_MONARCH_PATTERN})\b")

_SHORT_TITLE_RE = re.compile(
    r"(?:may be cited as|short title)[.\s\u2014]*[^.]{0,80}?(1[2-9]\d{2})",
    re.IGNORECASE,
)


# ── Core helpers ──────────────────────────────────────────────────────────


def resolve_monarch(text: str) -> tuple[str, int, int] | None:
    """Resolve a monarch name or abbreviation to (canonical_key, accession, end).

    Handles case variations, aliases, Latinised forms, and partial matches.
    Returns None for ambiguous names (e.g. "George" without a number).
    """
    lower = text.lower().strip()

    # Direct alias match
    if lower in MONARCH_ALIASES:
        canonical = MONARCH_ALIASES[lower]
        if canonical and canonical in REGNAL_YEAR_RANGES:
            start, end = REGNAL_YEAR_RANGES[canonical]
            return canonical, start, end

    # Try with trailing digits: "George5" → "Geo5", "Edward7" → "Edw7"
    match = re.match(r"([a-z]+?)(\d+)$", lower)
    if match:
        name, num = match.groups()
        for prefix in [name[:3], name[:4], name]:
            candidate = f"{prefix}{num}"
            if candidate in MONARCH_ALIASES:
                canonical = MONARCH_ALIASES[candidate]
                if canonical and canonical in REGNAL_YEAR_RANGES:
                    start, end = REGNAL_YEAR_RANGES[canonical]
                    return canonical, start, end

    return None


def compute_regnal_year(accession: int, end: int, session: int) -> int | None:
    """Convert a regnal session number to a calendar year.

    Validates the result against the monarch's reign bounds.
    The +1 tolerance on end handles edge cases at the end of a reign.
    """
    year = accession + session - 1
    if accession <= year <= end + 1:
        return year
    return None


# ── Deterministic strategies ──────────────────────────────────────────────
#
# Applied in order of specificity. Each returns a year or None.
# Strategies 1-2 handle well-formed URIs (fast path, covers ~90%).
# Strategies 3-9 handle OCR damage, nonstandard formatting, and freetext.
# Strategy 10 extracts years from legislation text content.


def _try_standard_uri(legislation_id: str) -> int | None:
    """Strategy 1-2: Standard numeric or canonical regnal year URI.

    Handles well-formed URIs where the year/monarch is at path segment [5]:
      http://www.legislation.gov.uk/id/ukpga/2018/12       → 2018
      http://www.legislation.gov.uk/id/ukla/Vict/44-45/12  → 1881
    """
    if not legislation_id:
        return None
    parts = legislation_id.split("/")
    if len(parts) < 6:
        return None

    year_part = parts[5]

    # Standard numeric year
    try:
        return int(year_part)
    except ValueError:
        pass

    # Canonical regnal year — match monarch prefix at position [5]
    # Only match clean segments (no underscores/dots that indicate nonstandard formatting)
    if "_" not in year_part and "." not in year_part:
        for prefix, (reign_start, _reign_end) in REGNAL_YEAR_RANGES.items():
            if year_part == prefix or year_part.startswith(prefix):
                if len(parts) > 6:
                    session_part = parts[6]
                    try:
                        session = int(session_part.split("-")[0])
                        return reign_start + session
                    except (ValueError, IndexError):
                        pass
                return reign_start

    return None


def _try_explicit_year(uri: str) -> int | None:
    """Strategy 3: Extract explicit 4-digit year from URI path or freetext.

    Handles:
      52 & 53 Vict. c. clviii (1889)  → extracts (1889)
      S.I. 1948 No. 955               → extracts 1948
      /ukpga/1845/18                   → extracts 1845
    """
    # Parenthesised year in freetext citations
    paren_match = re.search(r"\([^)]*?(\d{4})[^)]*?\)", uri)
    if paren_match:
        year = int(paren_match.group(1))
        if 1200 <= year <= 2026:
            return year

    # "S.I. YYYY" or "SI YYYY"
    si_match = re.search(r"(?i)S\.?I\.?\s*(\d{4})", uri)
    if si_match:
        year = int(si_match.group(1))
        if 1200 <= year <= 2026:
            return year

    # Standard URI path segments
    parts = uri.split("/")
    for part in parts:
        match = re.match(r"^(\d{4})$", part)
        if match:
            year = int(match.group(1))
            if 1200 <= year <= 2026:
                return year
    return None


def _try_regnal_with_separators(uri: str) -> int | None:
    """Strategy 4: Parse regnal years with nonstandard separators.

    Handles both freetext citations and URI paths with non-canonical formatting:
      52 & 53 Vict. c. clviii    (ampersand freetext)
      14 Geo. 6. c. xliii        (single session freetext)
      /52-53Vict/cxcvii          (concatenated session-monarch)
      /Vict_44_45/c12            (underscore-separated)
      /Vict/44/45/12             (slashes instead of dash)
    """
    # ── Pattern A: Freetext "N & N Monarch. c. ..." ──
    freetext_re = re.compile(
        r"(\d+)\s*[&]\s*\d+\s+"
        r"([A-Za-z]+)\.?\s*"
        r"(\d+)?",
        re.IGNORECASE,
    )
    match = freetext_re.search(uri)
    if match:
        session_str, monarch_name, monarch_num = match.groups()
        lookup = monarch_name.strip(".")
        if monarch_num:
            lookup = f"{lookup}{monarch_num}"
        monarch_info = resolve_monarch(lookup)
        if monarch_info:
            _, reign_start, reign_end = monarch_info
            try:
                session = int(session_str)
                year = compute_regnal_year(reign_start, reign_end, session)
                if year:
                    return year
            except ValueError:
                pass

    # "N Monarch. c. ..." without "&"
    single_re = re.compile(
        r"(\d+)\s+"
        r"([A-Za-z]+)\.?\s*"
        r"(\d+)?\.?\s*"
        r"c\.",
        re.IGNORECASE,
    )
    match = single_re.search(uri)
    if match:
        session_str, monarch_name, monarch_num = match.groups()
        lookup = monarch_name.strip(".")
        if monarch_num:
            lookup = f"{lookup}{monarch_num}"
        monarch_info = resolve_monarch(lookup)
        if monarch_info:
            _, reign_start, reign_end = monarch_info
            try:
                session = int(session_str)
                year = compute_regnal_year(reign_start, reign_end, session)
                if year:
                    return year
            except ValueError:
                pass

    # ── Pattern B: URI path segments ──
    parts = uri.split("/")
    try:
        start_idx = parts.index("id") + 2
    except ValueError:
        start_idx = 1 if len(parts) > 1 else 0

    if len(parts) <= start_idx:
        return None

    for i in range(start_idx, min(len(parts), start_idx + 5)):
        part = parts[i]

        # B1: Session-Monarch concatenated: "52-53Vict", "12-13Geo5"
        concat_re = re.compile(
            r"^(\d+)(?:-\d+)?[-_]?"
            r"([A-Za-z]+)[-_]?"
            r"(\d+)?$",
            re.IGNORECASE,
        )
        concat_match = concat_re.match(part)
        if concat_match:
            session_str, monarch_name, monarch_num = concat_match.groups()
            lookup = monarch_name
            if monarch_num:
                lookup = f"{monarch_name}{monarch_num}"
            monarch_info = resolve_monarch(lookup)
            if monarch_info:
                _, reign_start, reign_end = monarch_info
                try:
                    session = int(session_str)
                    if 1 <= session <= 70:
                        year = compute_regnal_year(reign_start, reign_end, session)
                        if year:
                            return year
                except ValueError:
                    pass

        # B2: Underscore-separated: "Vict_44_45" or "55-56_Vict"
        if "_" in part:
            segments = part.split("_")
            # Monarch first: "Vict_44_45"
            monarch_info = resolve_monarch(segments[0])
            if monarch_info:
                _, reign_start, reign_end = monarch_info
                for seg in segments[1:]:
                    try:
                        session = int(seg.split("-")[0])
                        year = compute_regnal_year(reign_start, reign_end, session)
                        if year:
                            return year
                    except (ValueError, IndexError):
                        continue
            # Session first: "55-56_Vict"
            for seg_idx, seg in enumerate(segments):
                try:
                    session = int(seg.split("-")[0])
                    for remaining in segments[seg_idx + 1:]:
                        monarch_info = resolve_monarch(remaining)
                        if monarch_info:
                            _, reign_start, reign_end = monarch_info
                            year = compute_regnal_year(reign_start, reign_end, session)
                            if year:
                                return year
                except ValueError:
                    continue

        # B3: Part is a monarch name — look at subsequent parts for session
        monarch_info = resolve_monarch(part)
        if not monarch_info:
            # Try stripping trailing digits: "Vict44"
            strip_match = re.match(r"([A-Za-z]+?)(\d+(?:-\d+)?)$", part)
            if strip_match:
                monarch_info = resolve_monarch(strip_match.group(1))
                if monarch_info:
                    _, reign_start, reign_end = monarch_info
                    try:
                        session = int(strip_match.group(2).split("-")[0])
                        year = compute_regnal_year(reign_start, reign_end, session)
                        if year:
                            return year
                    except (ValueError, IndexError):
                        pass
            continue

        _, reign_start, reign_end = monarch_info

        # Look at subsequent parts for session numbers
        for j in range(i + 1, min(len(parts), i + 4)):
            next_part = parts[j]

            # "44and45", "44_45", "44-45"
            session_match = re.match(r"(\d+)(?:and|-|_|/)(\d+)", next_part)
            if session_match:
                session = int(session_match.group(1))
                year = compute_regnal_year(reign_start, reign_end, session)
                if year:
                    return year

            # Plain number
            try:
                session = int(next_part)
                if 1 <= session <= 70:
                    year = compute_regnal_year(reign_start, reign_end, session)
                    if year:
                        return year
                break
            except ValueError:
                if next_part.lower().startswith(("c", "ch", "cap")):
                    continue
                break

    return None


def _try_combined_reign(uri: str) -> int | None:
    """Strategy 5: Handle combined reign references.

    Transition periods where two monarchs share a parliamentary session:
      /Edw8and1Geo6/...               → Edward VIII & 1 George VI → 1936
      1 Edw. 8. & 1 Geo. 6. c. lii   → freetext combined citation
      10-Edw-7-&-1-Geo-5-ch-1         → dash-separated combined reign
    """
    # URI path: "Edw8and1Geo6"
    combined_uri_re = re.compile(
        r"(?i)([A-Za-z]+\d?)and(\d*)([A-Za-z]+\d?)",
    )
    parts = uri.split("/")
    for part in parts:
        match = combined_uri_re.search(part)
        if match:
            _monarch1, session_str, monarch2_name = match.groups()
            monarch2_info = resolve_monarch(monarch2_name)
            if monarch2_info:
                _, reign_start, reign_end = monarch2_info
                session = int(session_str) if session_str else 1
                year = compute_regnal_year(reign_start, reign_end, session)
                if year:
                    return year

    # Freetext: "1 Edw. 8. & 1 Geo. 6. c."
    combined_freetext_re = re.compile(
        r"(?i)\d+\s+[A-Za-z]+\.?\s*\d+\.?\s*"
        r"[&]\s*"
        r"(\d+)\s+"
        r"([A-Za-z]+)\.?\s*"
        r"(\d+)?",
    )
    match = combined_freetext_re.search(uri)
    if match:
        session_str, monarch_name, monarch_num = match.groups()
        lookup = monarch_name.strip(".")
        if monarch_num:
            lookup = f"{lookup}{monarch_num}"
        monarch_info = resolve_monarch(lookup)
        if monarch_info:
            _, reign_start, reign_end = monarch_info
            try:
                session = int(session_str)
                year = compute_regnal_year(reign_start, reign_end, session)
                if year:
                    return year
            except ValueError:
                pass

    # Dash-separated: "10-Edw-7-&-1-Geo-5-ch-1"
    dash_combined_re = re.compile(
        r"(\d+)-([A-Za-z]+)-(\d+)-&-(\d+)-([A-Za-z]+)-(\d+)",
        re.IGNORECASE,
    )
    match = dash_combined_re.search(uri)
    if match:
        s1, m1_name, m1_num, s2, m2_name, m2_num = match.groups()
        # Try first monarch
        monarch_info = resolve_monarch(f"{m1_name}{m1_num}")
        if monarch_info:
            _, reign_start, reign_end = monarch_info
            session = int(s1)
            year = compute_regnal_year(reign_start, reign_end, session)
            if year:
                return year
        # Try second monarch
        monarch_info = resolve_monarch(f"{m2_name}{m2_num}")
        if monarch_info:
            _, reign_start, reign_end = monarch_info
            session = int(s2)
            year = compute_regnal_year(reign_start, reign_end, session)
            if year:
                return year

    return None


def _try_freetext_monarch(uri: str) -> int | None:
    """Strategy 6: Broad monarch matching with any extractable numbers.

    Last-resort regnal strategy — scans the URI for any monarch reference
    followed by numeric content.
    """
    for match in _REGNAL_RE.finditer(uri):
        canonical_key = match.group(1)
        if canonical_key not in REGNAL_YEAR_RANGES:
            for key in REGNAL_YEAR_RANGES:
                if key.lower() == canonical_key.lower():
                    canonical_key = key
                    break
            else:
                continue

        reign_start, reign_end = REGNAL_YEAR_RANGES[canonical_key]

        after_monarch = uri[match.end():]
        numbers = re.findall(r"(\d+)", after_monarch)
        for num_str in numbers[:3]:
            session = int(num_str)
            if 1 <= session <= 70:
                year = compute_regnal_year(reign_start, reign_end, session)
                if year:
                    return year

    return None


def _try_number_before_monarch(uri: str) -> int | None:
    """Strategy 7: Session number precedes monarch name.

    Handles reversed citation order common in OCR output:
      33 Vict.           → Victoria session 33
      5 Edw. 7.          → Edward VII session 5
      5-edw-7-c-138      → slug-style Edward VII session 5
      30Vict.c.8         → concatenated
    """
    pattern = re.compile(
        r"(\d+)"
        r"(?:\s*[-&]\s*\d+)?"
        r"\s*[-_.]?\s*"
        r"([A-Za-z]{3,})\.?\s*"
        r"[-_.]?(\d+)?",
        re.IGNORECASE,
    )
    for match in pattern.finditer(uri):
        session_str, monarch_name, monarch_num = match.groups()
        lookup = monarch_name.rstrip(".")
        if monarch_num:
            lookup = f"{lookup}{monarch_num}"
        monarch_info = resolve_monarch(lookup)
        if monarch_info:
            _, reign_start, reign_end = monarch_info
            try:
                session = int(session_str)
                if 1 <= session <= 70:
                    year = compute_regnal_year(reign_start, reign_end, session)
                    if year:
                        return year
            except ValueError:
                pass
    return None


def _try_embedded_year(uri: str) -> int | None:
    """Strategy 8: Year embedded in Act names or [UNCLEAR:] text.

    Handles years that are part of underscored/camelCase Act names:
      [UNCLEAR: Liverpool_Sanitary_Amendment_Act_1854_Cap.xv]
      local/Metropolitan_District_Railway_Act_1881_c.86
    """
    inner = uri
    unclear_match = re.search(r"\[UNCLEAR:\s*(.*?)\]?$", uri)
    if unclear_match:
        inner = unclear_match.group(1)

    matches = re.findall(r"(1[2-9]\d{2})", inner)
    if len(matches) == 1:
        year = int(matches[0])
        if 1200 <= year <= 2026:
            return year
    elif len(matches) > 1:
        for m in re.finditer(r"Act[_\s]*(1[2-9]\d{2})", inner):
            return int(m.group(1))
        return int(matches[0])
    return None


def _try_broad_year(uri: str) -> int | None:
    """Strategy 9: Extract any 4-digit year from URI freetext.

    Loosest pattern — scans the entire URI for year-like numbers:
      1949 No. 2170
      S.R. & O. 1948 No. 845
      Carlisle Corporation Act 1904
    """
    matches = re.findall(r"\b(1[2-9]\d{2}|20[0-2]\d)\b", uri)
    if len(matches) == 1:
        return int(matches[0])
    elif len(matches) > 1:
        for m in re.finditer(
            r"(?:Act\s+|Rules\s+|No\.\s*|S\.R\..*?|Order.*?)(\b(?:1[2-9]\d{2}|20[0-2]\d)\b)",
            uri,
        ):
            year = int(m.group(1))
            if 1200 <= year <= 2026:
                return year
        return int(matches[0])
    return None


def _try_short_title(text: str) -> int | None:
    """Strategy 10: Extract year from short title citation in section text.

    Looks for patterns like:
      "This Act may be cited as the Elementary Education Act 1891"
      "Short Title.—The Court of Session Act, 1868"
    """
    match = _SHORT_TITLE_RE.search(text)
    if match:
        year = int(match.group(1))
        if 1200 <= year <= 2026:
            return year
    return None


# ── Public API ────────────────────────────────────────────────────────────


def parse_legislation_year(
    legislation_id: str, *, text: str | None = None
) -> int | None:
    """Parse calendar year from a legislation ID and optional section text.

    This is the single entry point for all deterministic year extraction.
    Applies strategies in order of specificity — fast canonical parsing first,
    progressively looser patterns for damaged or nonstandard URIs, and finally
    text-based extraction from section content.

    Args:
        legislation_id: The legislation URI or identifier string.
        text: Optional section text content. If provided, enables short title
            extraction (strategy 10) as a final fallback.

    Returns:
        Calendar year as an integer, or None if no deterministic signal exists.
    """
    if not legislation_id:
        return None

    # Strategies 1-2: Standard and canonical regnal URIs (fast path)
    year = _try_standard_uri(legislation_id)
    if year is not None:
        return year

    # Strategy 3: Explicit year in URI
    year = _try_explicit_year(legislation_id)
    if year is not None:
        return year

    # Strategy 4: Regnal with nonstandard separators
    year = _try_regnal_with_separators(legislation_id)
    if year is not None:
        return year

    # Strategy 5: Combined reign references
    year = _try_combined_reign(legislation_id)
    if year is not None:
        return year

    # Strategy 6: Freetext monarch scanning
    year = _try_freetext_monarch(legislation_id)
    if year is not None:
        return year

    # Strategy 7: Number-before-monarch patterns
    year = _try_number_before_monarch(legislation_id)
    if year is not None:
        return year

    # Strategy 8: Embedded year in Act names
    year = _try_embedded_year(legislation_id)
    if year is not None:
        return year

    # Strategy 9: Broad year extraction
    year = _try_broad_year(legislation_id)
    if year is not None:
        return year

    # Strategy 10: Short title from text content
    if text:
        year = _try_short_title(text)
        if year is not None:
            return year

    return None
