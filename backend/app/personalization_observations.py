"""Narrow experiment diagnostics. Never a commit gate, judge or retry policy."""
from app.llm_capture import CapturingClient
import re

from app.profile_instructions import HEADINGS, SUMMARY
from app.profiles import SummaryBullets

# Deliberately small documented set; this is NOT Unicode Emoji compliance.
EMOJI_SCOPE = "day12-common-v1: U+1F600–1F64F, U+1F44D/U+1F44E/U+1F680/U+1F4A1, U+2705/U+274C/U+26A0/U+2728/U+2764"
EMOJI = re.compile("[\U0001f600-\U0001f64f\U0001f44d\U0001f44e\U0001f680\U0001f4a1\u2705\u274c\u26a0\u2728\u2764]")
MARKERS = ("ORION-17", "RC-42", "Checkout", "MVI")


def check(correct, detail=""):
    return {"status": "unavailable" if correct is None else "pass" if correct else "fail",
            "correct": correct, "detail": detail}


def markdown_parts(text):
    """H2 and list markers outside backtick/tilde fences; code counts as section content."""
    headings, contents, count = [], [], 0
    fence = None
    for line in text.splitlines():
        if fence:
            if re.fullmatch(r" {0,3}" + re.escape(fence[0]) + "{" + str(fence[1]) + r",}\s*", line):
                fence = None
            elif contents and line.strip():
                contents[-1] = True
            continue
        opening = re.match(r"^ {0,3}(`{3,}|~{3,})(.*)$", line)
        if opening and not (opening[1][0] == "`" and "`" in opening[2]):
            fence = (opening[1][0], len(opening[1]))
            continue
        heading = re.fullmatch(r" {0,3}##\s+(.+?)\s*", line)
        if heading:
            headings.append(heading[1])
            contents.append(False)
            continue
        if re.match(r"^\s*(?:[-+*]|\d+[.)])\s+\S", line):
            count += 1
        if contents and line.strip():
            contents[-1] = True
    return headings, contents, count


def output_checks(profile, outcome):
    usable = outcome.status == "completed" and bool(outcome.reply)
    text = outcome.reply if usable else ""
    headings, contents, count = markdown_parts(text)
    fmt = profile.response_format
    checks = {}
    if isinstance(fmt, SummaryBullets):
        checks["summary"] = check(bool(headings) and headings[0] == SUMMARY[profile.language]
                                  and contents[0] if usable else None)
        checks["list_limit"] = check(count <= fmt.max_bullets if usable else None,
                                      f"{count}/{fmt.max_bullets}" if usable else outcome.status)
    else:
        checks["headings"] = check(headings == list(HEADINGS[profile.language]) if usable else None)
        checks["nonempty_sections"] = check(len(contents) == 4 and all(contents) if usable else None)
    if profile.constraints.no_emoji:
        checks["no_emoji"] = check(not EMOJI.search(text) if usable else None, EMOJI_SCOPE)
    markers = {marker: check(marker in text if usable else None, "literal mention") for marker in MARKERS}
    return checks, markers
