<!--
Delete a heading only if it genuinely does not apply, and say why where you do.
An empty heading is more readable than a removed one.
-->

## What changed

<!-- What this pull request does, in the plainest sentence that is still true. -->

## What failure this prevents

<!--
Not what it improves. What goes wrong without it, and how you know that failure
is real rather than imagined.
-->

## Evidence

<!--
Every number in this body carries the command that produced it, run at the
commit being pushed and not in your working tree. Paste the command and what it
printed.

A number you cannot back with a command is a claim. Write it as a claim; that is
a legitimate thing to do here and pretending otherwise is not.

Where this adds or changes a guard, the evidence is the guard refusing the thing
it names. Break it on purpose, show it red, put it back.
-->

## Does this touch a frozen parameter?

<!--
Yes or no, and if yes, which one.

This is asked separately because it is the one class of change whose cost is not
visible in the diff. A frozen value is amended by adding a new freeze record
carrying what was wrong and how it was found, never by editing the old record,
and a result already published under the superseded freeze stays published under
it. See docs/decisions/pre-registration.md.

Until milestone 7 lands there is no frozen file, and the honest answer is "no,
nothing is frozen yet".
-->

## What this does not cover

<!--
What you did not check, what you could not check, and what you left open. A
negative disclosure here stays negative through every later edit of this body.
-->

<!--
Before you push: every commit needs a Signed-off-by trailer matching its author.
`git commit -s` writes it, and the DCO sign-off check refuses the pull request
without it. See CONTRIBUTING.md.
-->
