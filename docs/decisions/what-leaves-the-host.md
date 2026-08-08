# What a run may send off the host

Decided in issue #13.

This board simulates, so the reflex answer is that no personal data is involved.
That reflex is wrong in two ordinary places, and both of them are places where
the data arrives without anybody choosing to put it there.

The first is provenance. Output files carry metadata about the run that produced
them, and the obvious things to reach for are the username, the hostname, the
absolute path of the working directory and the machine's environment. Those
identify a person and a machine. A spectrogram published as supplementary
material carries them into public view, and nobody decided that it should.

The second is input. Once a real measured trace can be read, the operator's own
files enter the process, and files that came off a beamline carry proposal
numbers, institution names and the names of the people who took the data.
Anything the tool copies out of an input file and into an output file leaves the
host when that output is shared.

## No network by default

No code path a normal run reaches makes a network call. Not a version check, not
a telemetry ping, not a lazy fetch of a constant table, not an upload of a result.

A run produces its output from its manifest and the tree, and a machine with no
route to the internet runs it to completion. That is also what makes a result
reproducible offline, which milestone 10 and milestone 11 both need, so the
privacy rule and the reproducibility rule are the same rule here.

## What provenance may contain

An output file's provenance is limited to what identifies the software and the
parameters. The allowlist, and nothing beyond it:

The version of the software that produced the file.

The manifest hash.

The seeds the run consumed.

What is excluded, named rather than left to the allowlist to imply: the username,
the hostname, the machine's domain, the absolute path of the working directory or
of any input file, the environment, the wall clock time of the run.

Excluding the timestamp deserves its own sentence, because it is the one somebody
will want back. A timestamp is weak identifying information on its own and strong
in combination, it is not needed to reproduce anything, and it would break the
byte identical requirement in
[determinism-and-seeding.md](determinism-and-seeding.md) anyway. The reason to
leave it out is therefore not only privacy, and the requirement it breaks is
enforced independently.

The allowlist is a list of what may go in, not a list of what to strip out. A
field nobody thought about is absent by default rather than present until
somebody notices it.

## Metadata read out of an input file

Not copied into an output file unless the operator asks for it.

The default is exclusion, and asking is a visible act naming the fields. This is
the rule with no code to be true of yet, because nothing here reads a measured
trace, and it is written now because the moment it stops being hypothetical is the
moment somebody is adding a reader.

## Federation is a command, not a side effect

Publishing a run anywhere off the host is a separate command the operator
invokes deliberately. It states what it is about to send before it sends it, and
it never runs as a consequence of producing a result.

A command that sends and a command that computes are different commands. Once one
command does both, the operator cannot choose one without the other, and the
choice was the entire protection.

## Where the operator reads this

In the documentation an operator meets before running the tool, which means the
README and the install and run instructions, and not in a policy file nobody
opens.

A statement that is true of the code and invisible to the operator has protected
nobody. This document is the record of the decision; it is not the disclosure,
and it does not discharge the obligation to put the disclosure where it will be
read.

## The issues that make each of these true in code

None of it is true in code today and this section is the list of what is owed
rather than a description of what exists.

The no network default and the deliberate federation command are issue #45. They
are one issue because they are one property: the network has exactly one exit and
everything else is refused. That issue also carries the greppable form of the
refusal and, in its own body, what a text rule over the source cannot catch.

The provenance allowlist is issue #24, which builds the run manifest, and issue
#25, which writes it into a file. The allowlist is a property of what those two
put in, so a field excluded here has to be a field the manifest never carries
rather than a field the writer drops.

The rule on input metadata is issue #46.

Where the operator reads it has no issue of its own. It belongs to whichever
change first gives an operator a command to run, and it is a requirement on that
change rather than a task beside it.
