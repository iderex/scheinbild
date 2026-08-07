# Security

## What the realistic surface is

This repository is a simulation and an analysis. It is not a service, it holds
no credentials, and it opens no ports. Listing generic categories here would
describe a threat model this project does not have.

The surface that is real is the file reader. Code here ingests a spectrogram
file, a run manifest and a table of atomic data, and a reader that parses an
attacker-supplied file is the one place in this tree where hostile bytes meet
code. A crafted file that crashes the reader, exhausts memory, or causes the
reader to execute anything, is a vulnerability in this repository.

The second surface is a run that sends something off the operator's machine.
Personal data and experimental data are meant to stay on the machine they were
put on. A code path that ships either of them somewhere without the operator
deliberately asking for it is a defect worth reporting through this route, even
if nothing about it looks like a classical vulnerability.

## Where to report

Use GitHub's private vulnerability reporting on this repository, under the
Security tab. It is private to the maintainer and it keeps the report and any
fix together.

Include what you fed the code, what happened, and the command you ran. A report
with a file that reproduces the behaviour is worth several without one.

## Where not to report

Not in a public issue, and not in a pull request, if the report describes a way
to make the code do something it should not. Those are public the moment you
write them, and a fix takes longer to land than a reader takes to find it.

An ordinary bug that is not a security problem belongs in a public issue.
Crashes on your own malformed file, wrong numbers, and confusing errors are
ordinary bugs. If you are unsure which you have, use the private route and it
can be moved.

## What to expect

The maintainer is one person. A report will be read and answered. There is no
service level agreement here and stating one would be a promise nothing backs.

## What is out of scope

Anything about the physics being wrong. That is the argument this board exists
to have, and it belongs in a public issue where it can be argued with.
