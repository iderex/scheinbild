"""The one deliberate way anything leaves this host.

The rule is in ../../docs/decisions/what-leaves-the-host.md. No code path a
normal run reaches makes a network call, and publishing a run anywhere off the
host is a separate command the operator invokes, which states what it is about
to send before it sends it.

Both halves are one property rather than two features. The network has exactly
one exit and everything that is not that exit is refused. Split them and you get
either a refusal with an undeclared exception in it, or an exit with nothing
holding the rest of the tree away from the network.

## What may be sent

The provenance allowlist, and nothing outside it: the version of the software,
the manifest hash, and the seeds the run consumed. It is a list of what may go
in rather than a list of what to strip out, so a field nobody thought about is
absent by default rather than present until somebody notices it.

`refuse_anything_outside_the_allowlist` is the sentence made into a function.
Anything reaching the sending seam goes through it, so an extra key is refused at
the moment it would leave rather than reviewed for at the moment it is added.

The parameters of a run are deliberately not on that list. They are in the file
the operator is publishing, and what this command adds beside the file is the
three fields above.

## Nothing is sent today, and that is not a formality

`send` is a seam and its only implementation refuses. No destination has been
decided anywhere on this board, no federation protocol exists, and inventing one
here would be deciding something in a branch that belongs in an issue.

So the honest statement of what this module does today is: it builds the payload,
it prints exactly what would be sent, it stops unless the operator says yes, and
then it refuses because there is nowhere to send to. What that buys already is
the shape. The confirmation, the preview and the allowlist are in place before a
transport exists, rather than being asked for afterwards from a command that was
already sending.

## Reachable from no other command

Nothing else in this package imports this module, and the suite has a test
saying so. A command that sends and a command that computes are different
commands: once one does both, the operator cannot choose one without the other,
and the choice was the entire protection.
"""

import sys
from pathlib import Path
from typing import Callable, Mapping

from scheinbild_model.manifest import Manifest
from scheinbild_model.spectrogram_file import read

# What provenance may contain, from the decision, in the order a reader wants to
# see it. Anything not named here may not leave.
ALLOWED_PROVENANCE = ("code_version", "manifest_digest", "seeds")

# Named in the decision as excluded rather than left to the allowlist to imply.
# Held here so the refusal message can say which of them somebody reached for,
# and so a reader of this file sees what the rule is about rather than only what
# it permits.
NAMED_EXCLUSIONS = (
    "username",
    "hostname",
    "domain",
    "working_directory",
    "input_path",
    "environment",
    "wall_clock_time",
)


class PublishRefused(RuntimeError):
    """Something was going to leave the host that may not, or could not."""


def provenance_of(manifest: Manifest) -> dict[str, object]:
    """The three allowlisted fields, and nothing else, out of a manifest."""
    return {
        "code_version": manifest.code_version,
        "manifest_digest": manifest.digest(),
        "seeds": dict(manifest.seeds),
    }


def refuse_anything_outside_the_allowlist(payload: Mapping[str, object]) -> None:
    """Refuse a payload carrying a field the allowlist does not permit."""
    extra = [key for key in payload if key not in ALLOWED_PROVENANCE]
    if extra:
        named = [key for key in extra if key in NAMED_EXCLUSIONS]
        detail = (
            f" {sorted(named)} are excluded by name in the decision." if named else ""
        )
        raise PublishRefused(
            f"The payload carries {sorted(extra)}, and provenance is limited to "
            f"{list(ALLOWED_PROVENANCE)}.{detail} The allowlist is what may go "
            "in rather than what to strip out, so a field nobody thought about "
            "is absent rather than present until somebody notices it. See "
            "docs/decisions/what-leaves-the-host.md."
        )
    missing = [key for key in ALLOWED_PROVENANCE if key not in payload]
    if missing:
        raise PublishRefused(
            f"The payload is missing {missing}. A published file whose "
            "provenance is incomplete cannot be checked against the run that "
            "produced it, which is what the allowlist exists to carry."
        )


def describe(path: Path, payload: Mapping[str, object]) -> str:
    """Exactly what would be sent, in a form an operator can read.

    Printed before anything is sent, and it is the whole payload rather than a
    summary of it. A preview that leaves a field out is worse than none, because
    it is what the operator will believe.
    """
    lines = [
        "This would send the following, and nothing else.",
        "",
        f"  the file: {path}",
        "",
        "  provenance:",
    ]
    for key in ALLOWED_PROVENANCE:
        lines.append(f"    {key}: {payload[key]!r}")
    lines += [
        "",
        "  not sent, excluded by name in docs/decisions/what-leaves-the-host.md:",
        f"    {', '.join(NAMED_EXCLUSIONS)}",
    ]
    return "\n".join(lines)


def send(path: Path, payload: Mapping[str, object]) -> None:
    """The only place in this tree where anything would leave the host.

    It refuses. No destination has been decided on this board, so there is
    nowhere for this to go, and a transport written here would be deciding that
    in a branch. The refusal is the current state of the world rather than a
    placeholder that quietly does nothing.
    """
    refuse_anything_outside_the_allowlist(payload)
    raise PublishRefused(
        f"Nothing was sent. {path} was prepared and confirmed, and this build "
        "has no destination to send it to: where a run is published, and by "
        "what protocol, is not decided anywhere on this board. This is the one "
        "place in the tree that would make a network call, and it does not make "
        "one."
    )


def publish(
    path: Path,
    ask: Callable[[str], str],
    out: Callable[[str], None],
    sender: Callable[[Path, Mapping[str, object]], None] = send,
) -> int:
    """Prepare, show, confirm, and only then reach the sending seam.

    `ask` and `out` are passed in rather than reached for, so the suite drives
    this without a terminal and without a network, and so the order of the four
    steps is visible in one function instead of spread through a command line
    parser.
    """
    spectrogram = read(path)
    payload = provenance_of(spectrogram.manifest)
    refuse_anything_outside_the_allowlist(payload)

    out(describe(path, payload))
    out("")
    answer = ask("Send this? Type yes to send, anything else to stop: ")

    if answer.strip().lower() != "yes":
        out("Nothing was sent.")
        return 1

    sender(path, payload)
    return 0


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        print("usage: python -m scheinbild_model.publish <spectrogram.npz>")
        return 2
    try:
        return publish(Path(argv[0]), ask=input, out=print)
    except PublishRefused as refused:
        print(str(refused), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
