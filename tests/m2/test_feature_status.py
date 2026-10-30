"""Enforces the rule "every release PR updates docs/FEATURE_STATUS.md" (docs/RELEASE_NOTE_TEMPLATE.md rule 7).

Stdlib only, no network, fast. Checks (offline, against the files in the repository):
  (a) the summary tables (by status, by release, design rows) equal a recount of the feature-table rows;
  (b) the machine-readable line "Merged PRs: n, n, ..." exists, and every PR number cited in the feature tables
      (PR column, except entries marked open) is in it;
  (c) every PR number named in the HANDOFF.md lines that say "merged" is in that block.
`check` is pure so that the test can prove it fails on a deliberately stale table (temp text, not the real file).
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STATUSES = ("done", "partial", "pending", "dropped")
RELEASES = ("R25", "R26", "P1", "M1", "M2", "M3", "M4", "M5", "RQ", "later")


def _cells(line):
    return [c.strip() for c in line.strip().strip("|").split("|")]


def parse(text):
    lines = text.split("\n")
    s3 = next(i for i, l in enumerate(lines) if l.startswith("## 3."))
    s4 = next(i for i, l in enumerate(lines) if l.startswith("## 4."))
    rows, design = [], True
    for l in lines[s3:s4]:
        if l.startswith("### "):
            design = "design rows" in l
        elif l.startswith("| ") and not l.startswith("| Id ") and not l.startswith("|---"):
            c = _cells(l)
            assert len(c) == 7, l
            rows.append({"id": c[0], "status": c[2].split()[0], "release": c[3], "prs": c[4], "design": design})
    return lines, rows


def summary_tables(lines):
    by_status, by_release = {}, {}
    for l in lines:
        if not l.startswith("| "):
            continue
        c = _cells(l)
        if c[0] in STATUSES + ("total",) and len(c) == 3:
            by_status[c[0]] = (int(c[1]), int(c[2]))
        elif c[0] in RELEASES + ("all",) and len(c) == 6:
            by_release[c[0]] = tuple(int(x) for x in c[1:])
    return by_status, by_release


def merged_block(lines):
    for l in lines:
        if l.startswith("Merged PRs:"):
            return {int(x) for x in re.findall(r"\d+", l)}
    return None


def check(text, handoff):
    errors = []
    lines, rows = parse(text)
    by_status, by_release = summary_tables(lines)
    for s in STATUSES:
        want_all = sum(1 for r in rows if r["status"] == s)
        want_design = sum(1 for r in rows if r["status"] == s and r["design"])
        if by_status.get(s) != (want_design, want_all):
            errors.append("status %s: table says %s, recount (design, all) = %s" % (s, by_status.get(s), (want_design, want_all)))
    if by_status.get("total") != (sum(1 for r in rows if r["design"]), len(rows)):
        errors.append("total row does not match the recount")
    for k in RELEASES:
        want = tuple(sum(1 for r in rows if r["release"] == k and r["status"] == s) for s in STATUSES)
        want = want + (sum(want),)
        if by_release.get(k) != want:
            errors.append("release %s: table says %s, recount %s" % (k, by_release.get(k), want))
    wall = tuple(sum(1 for r in rows if r["status"] == s) for s in STATUSES)
    if by_release.get("all") != wall + (len(rows),):
        errors.append("release 'all' row does not match the recount")
    block = merged_block(lines)
    if block is None:
        errors.append("no 'Merged PRs:' line")
        return errors
    for r in rows:
        for m in re.finditer(r"\b(\d{2,3})\b(?!\s*\(open)", r["prs"]):
            n = int(m.group(1))
            if n not in block:
                errors.append("%s cites PR %d which is not in the Merged PRs block (mark it open or add it)" % (r["id"], n))
    for l in handoff.split("\n"):
        if re.search(r"\bmerged\b", l) and l.startswith("- ") and "(open)" not in l:
            for n in re.findall(r"PR (\d+)", l):
                if int(n) not in block:
                    errors.append("HANDOFF says PR %s merged but it is not in the Merged PRs block" % n)
    return errors


def _real():
    return (ROOT / "docs" / "FEATURE_STATUS.md").read_text(encoding="ascii"), (ROOT / "HANDOFF.md").read_text(encoding="ascii")


def test_feature_status_matches_its_tables():
    text, handoff = _real()
    assert check(text, handoff) == []


def test_check_fails_on_a_stale_table():
    text, handoff = _real()
    stale = text.replace("| done | ", "| done | 1", 1)  # corrupt the first summary count
    assert any("status done" in e for e in check(stale, handoff))
    no_block = "\n".join(l for l in text.split("\n") if not l.startswith("Merged PRs:"))
    assert any("Merged PRs" in e for e in check(no_block, handoff))
    assert any("not in the Merged PRs block" in e for e in check(text, handoff + "\n- PR 99999 merged\n"))
    bad_row = text.replace("| M3-1 | Surface, term structure and skew builder | pending |", "| M3-1 | Surface, term structure and skew builder | done |", 1)
    assert bad_row != text and check(bad_row, handoff)


def test_check_fails_on_a_stale_pr_cell():
    text, handoff = _real()
    stale = text.replace("| P1-1 | Version bump 0.2.0a1 and sibling pins | done | P1 | 63, 66 |", "| P1-1 | Version bump 0.2.0a1 and sibling pins | done | P1 | 63, 66, 99999 |", 1)
    assert stale != text and any("99999" in e for e in check(stale, handoff))
