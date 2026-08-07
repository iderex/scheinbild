# The implementation means

Decided in issue #2.

## What was chosen

Python, with the reproducibility cost paid explicitly rather than assumed away.

## What the board has to do

The choice was made against the work, not against habit. The work is dense two
dimensional arrays over an energy grid and a delay grid, Fourier transforms,
numerical integration of a pulse envelope, nonlinear least squares fitting, a
test suite that can refuse a property rather than merely observe it,
deterministic floating point across machines, and an artefact an operator can
run without a build farm.

One requirement outranks the rest. A result nobody in the field can re-run has
failed at the only thing it was for, and the people who have to be able to check
this work are atomic physicists.

## Why Python

It is what the field reads and writes. A physicist who disagrees with a model
choice here can open the file, follow it, change it and re-run it, without first
learning a language to do so. Numpy and scipy cover every numerical need above
with libraries that are already trusted in this domain.

## What Python costs, and how each cost is paid

Floating point results are not automatically reproducible across linear algebra
builds and thread counts. Paid by pinning the interpreter to a single minor
release, pinning every dependency, forcing single threaded linear algebra in any
run that produces a published number, and making byte identical output a checked
property rather than a hope. The rule that does this is in
[determinism-and-seeding.md](determinism-and-seeding.md).

The dependency surface is wide. Paid by a committed lockfile that the gate
installs from without resolving, so that a green run says something about the
graph an operator will actually get.

Packaging a runnable artefact takes deliberate work. Paid by treating a clean
clone and a documented command as a requirement of the first release rather than
as something that will fall out of the build.

None of these are discharged by this document. Each is a property some later
check has to refuse a violation of, and until such a check exists the cost is
stated and unpaid.

## What was rejected, and why

Rust. It gives determinism and a single binary artefact almost for free and it
has the strongest refusal story of the candidates. The numerical ecosystem is
thinner than numpy and scipy. The decisive cost is the audience: handing the
people who have to check this work a language most of them do not read converts
a verifiable claim into one they have to take on trust, which is the failure
this board exists to argue against.

Julia. Good at exactly this kind of numerics. It adds a runtime nothing else
here carries, and its cross version reproducibility story is not better than a
pinned Python, so the runtime buys nothing that was the reason for looking.

C++ and Fortran. What the large calculations in this field are written in, which
is a real argument for them. Build reproducibility and the test harness cost
more here than the numerical performance is worth, and nothing in this model is
large.

## What would change the answer

Any one of these, on its own:

A numerical requirement appears that numpy and scipy cannot carry at the
accuracy or the scale needed, and the working alternative exists in another
language.

Byte identical output across the three supported operating systems turns out not
to be reachable in pinned Python at acceptable cost. The measurement that shows
this, not the suspicion that it might, is what reopens the question.

The audience argument stops holding, because the readers who have to check the
work are no longer the ones this choice was made for.

The choice is revisited by amending this document with the reason and the date,
and by opening the issue that carries the migration. It is not revisited by a
new artefact quietly arriving in a different means.
