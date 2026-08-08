"""Refuse the formatting defects in tracked Markdown that a reader cannot see.

Four properties, all of them about bytes rather than about prose:

A tracked document is stored with LF line endings. A carriage return in the
stored bytes makes every later diff of that file unreadable on the other two
platforms.

No line ends in whitespace. Trailing whitespace is invisible where it is written
and visible in every diff that touches the line, so it moves the cost from the
person who made it to the next person.

Every document ends in exactly one newline. A file with no final newline makes
the last line of the next change look like a rewrite of a line nobody touched.

No hard tab. A tab renders at a width the reader's tool chooses, so an indented
code block containing one says a different thing to two readers.

## Why this is not a Markdown formatter

A general Markdown formatter was measured against this corpus first and is not
what landed. Every one of them normalises, and normalising this corpus means
rewriting it: the documents here use indented code blocks throughout, a
formatter rewrites those as fenced blocks, and a paragraph whose line break
falls inside a code span comes back joined into a line wider than the corpus
wraps at. That is a change to what the documents say they are, arriving as a
side effect of a check about whitespace. The properties above are the ones worth
refusing, they are refusable without touching a single line of prose, and the
corpus already holds all four.

What that gives up is stated rather than left to be found. Nothing here judges
heading style, list markers, link form, the width prose wraps at, or whether a
code block is indented or fenced. Those are conventions this corpus keeps by
hand, and a reader who breaks one gets no red row.

## Where it reads from

The stored bytes, out of git, and never the working copy. That is the whole
answer to the line-ending trap. A Windows clone checks a document out with
carriage returns and a Linux runner checks the same commit out without them, so
a check that reads the working copy tells a Windows contributor that every
document in the tree is broken on a tree they have not modified. Reading the
blob makes both sides judge the same bytes, and the noise cannot arise.

The fix mode writes the working copy, because that is the only thing a person
can edit and commit.
"""

import argparse
import subprocess
import sys

_LF = b"\n"
_CR = b"\r"
_TAB = b"\t"

FIX_COMMAND = "python -m tools.docs_format --fix"


class Defect:
    """One property, broken in one file, with the line it was broken on.

    Carries the line number because the message a reader acts on is the one that
    says where to look, and a file name on its own sends them to read the whole
    document.
    """

    def __init__(self, path: str, line: int | None, rule: str, detail: str):
        self.path = path
        self.line = line
        self.rule = rule
        self.detail = detail

    def __str__(self) -> str:
        where = self.line
        return f"{where}: {self.rule}: {self.detail}"


def tracked_documents() -> list[str]:
    """Every tracked Markdown path, from git rather than from a walk.

    A walk finds an untracked scratch document and fails the gate on a file that
    is not in the tree; it also misses nothing, which is the half that sounds
    like an argument for it. Asking git gets the set the check is about.
    """
    listed = subprocess.run(
        ["git", "ls-files", "*.md"],
        capture_output=True,
        text=True,
        check=True,
    )
    return listed.stdout.split(  )


def stored_bytes(path: str) -> bytes:
    """The bytes git holds for a path at HEAD, not the bytes on disk."""
    shown = subprocess.run(
        ["git", "show", f"HEAD:{path}"],
        capture_output=True,
        check=True,
    )
    return shown.stdout


def inspect(path: str, content: bytes) -> list[Defect]:
    """Every defect in one document's bytes, in the order a reader meets them."""
    defects: list[Defect] = []

    lines = content.split(_LF)
    for number, line in enumerate(lines, start=1):
        if _CR in line:
            defects.append(
                Defect(
                    path,
                    number,
                    "carriage-return",
                    "the stored bytes carry a carriage return, so this file "
                    "reads as changed on a platform that stores LF",
                )
            )
        if _TAB in line:
            defects.append(
                Defect(
                    path,
                    number,
                    "hard-tab",
                    "a hard tab renders at a width the reader's tool chooses, "
                    "so two readers see different indentation",
                )
            )

    # The last element of a split on LF is what follows the final newline. It is
    # empty when the file ends in one, which is the only shape allowed here.
    if content and lines[-1] != b"":
        defects.append(
            Defect(
                path,
                len(lines),
                "no-final-newline",
                "the file does not end in a newline, so the next change to its "
                "last line reads as a rewrite of a line nobody touched",
            )
        )

    # Checked after the final newline rule and against the lines before it, so a
    # file ending in one newline is not reported for the empty string that
    # follows it.
    #
    # The carriage return is taken off first, so a CRLF line is one defect under
    # the rule that owns the byte rather than two under two rules. A reader who
    # gets both reads the second as a separate thing to fix and goes looking for
    # a space that is not there.
    for number, line in enumerate(lines[:-1], start=1):
        line = line.removesuffix(_CR)
        if line != line.rstrip():
            defects.append(
                Defect(
                    path,
                    number,
                    "trailing-whitespace",
                    "the line ends in whitespace, which is invisible where it "
                    "was written and visible in every later diff",
                )
            )

    return defects


def repair(content: bytes) -> bytes:
    """The bytes this file should hold, for the three defects that have one fix.

    A hard tab has no repair here on purpose. What replaces it depends on what
    it was standing in for, and a check that guesses produces a diff nobody
    asked for inside a code block whose alignment was the point.
    """
    repaired = content.replace(_CR + _LF, _LF).replace(_CR, _LF)
    repaired = _LF.join(line.rstrip() for line in repaired.split(_LF))
    if repaired and not repaired.endswith(_LF):
        repaired += _LF
    return repaired


def check(paths: list[str]) -> list[Defect]:
    defects: list[Defect] = []
    for path in paths:
        defects.extend(inspect(path, stored_bytes(path)))
    return defects


def fix(paths: list[str]) -> list[str]:
    """Repair the working copy. Returns the paths that changed."""
    changed = []
    for path in paths:
        with open(path, "rb") as handle:
            before = handle.read()
        after = repair(before)
        if after != before:
            with open(path, "wb") as handle:
                handle.write(after)
            changed.append(path)
    return changed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Refuse formatting defects in tracked Markdown. Reads the bytes "
            "git stores, so a working copy checked out with a different line "
            "ending convention is judged the same on every platform."
        )
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--check",
        action="store_true",
        help="report defects and exit non-zero if there are any",
    )
    mode.add_argument(
        "--fix",
        action="store_true",
        help="repair what can be repaired in the working copy",
    )
    parser.add_argument(
        "paths",
        nargs="*",
        help="documents to read; every tracked .md when none are given",
    )
    arguments = parser.parse_args(argv)

    paths = arguments.paths or tracked_documents()

    if arguments.fix:
        for path in fix(paths):
            print(f"repaired {path}")
        return 0

    defects = check(paths)
    for defect in defects:
        print(str(defect))
    if defects:
        print(
            f"{len(defects)} defect(s) in tracked Markdown. Repair the "
            f"carriage returns, the trailing whitespace and the missing final "
            f"newlines with: {FIX_COMMAND}. A hard tab has no automatic "
            f"repair, because what replaces it depends on what it was standing "
            f"in for. Commit the repair before running this again: the check "
            f"reads the bytes git stores and not your working copy, which is "
            f"what stops a checkout with other line endings from reporting "
            f"every document in the tree.",
            file=sys.stderr,
        )
        return 1
    print(f"{len(paths)} tracked document(s) checked, no defects.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
