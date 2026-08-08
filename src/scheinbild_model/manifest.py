"""The run manifest, and the hash that identifies it.

A manifest is the complete description of a run. Every parameter the model
reads, every seed it consumes, the version of the code, and nothing else. If a
value influences the output and is not in the manifest, the manifest is wrong,
and the arrangement here is meant to make that true rather than to intend it.

The way it is made true is that a parameter is read through a manifest or it is
not read at all. There is no default to fall back to, no environment lookup and
no module level value a function could pick up instead, so a parameter the
manifest does not carry is a parameter the model cannot reach. A manifest
assembled alongside a run would drift the first time somebody added an argument;
this one cannot, because the argument would have nowhere to come from.

The rule this serves is in ../../docs/decisions/determinism-and-seeding.md, and
the freeze record in ../../docs/decisions/pre-registration.md is built on the
hash below.

## What the hash is over

The parsed content, not the bytes. A manifest that is reformatted, or whose keys
are written in a different order, or that was written out by a different machine,
has to hash the same, because a hash that moves for a formatting reason makes the
freeze record worthless: every result would need re-freezing after a whitespace
change, and nobody would keep doing that.

So the digest is taken over a canonical form built here rather than over any file
on disk. The form sorts its keys, writes each float as its exact hexadecimal
representation rather than as a decimal rendering, tags every value with its
type, and joins its lines with a single newline that does not depend on the
platform. `canonical_form` returns it, so what was hashed is readable rather
than having to be trusted.

Floats are written with `float.hex`, which is exact and round trips. A decimal
rendering is the obvious alternative and it is the one that would fail quietly:
`repr` is exact on this interpreter today, and the moment a manifest is written
out and read back through anything that shortens a decimal, two runs that are
bit for bit identical hash differently.

Keys that could break the form are refused rather than escaped. A key holding a
tab or a newline could be built to collide with a different manifest, and
refusing it costs nothing because no parameter of this model wants one.
"""

import hashlib
from dataclasses import dataclass
from math import isfinite
from types import MappingProxyType
from typing import Mapping, Union

# The label that opens the canonical form. It is versioned because the form is
# what the freeze record's hashes were taken over: if the form ever has to
# change, every hash changes with it, and a reader comparing an old record with
# a new run has to be able to see that rather than conclude the parameters
# moved.
CANONICAL_FORM_VERSION = "scheinbild-manifest/1"

# What a parameter may be. Restricted deliberately. Anything outside this set
# has no canonical rendering that is stable across machines, so it could not be
# hashed to the rule above, and a value the hash cannot see is a value the
# freeze record does not cover.
ParameterValue = Union[bool, int, float, str]

_FORBIDDEN_IN_A_NAME = ("\t", "\n", "\r")


class ManifestRefused(ValueError):
    """A manifest was offered that could not be a complete description of a run."""


class ParameterNotInManifest(KeyError):
    """The model asked for a parameter the manifest does not carry.

    Raised rather than defaulted. A default is a value that influences the
    output and is not in the manifest, which is the one thing the manifest type
    exists to make impossible.
    """


class SeedNotInManifest(KeyError):
    """The model asked for a seed the manifest does not carry.

    Same reason as the parameter case, and worse in its consequences: a seed
    that comes from anywhere but the manifest makes two runs of the same
    manifest differ, which is the property the reproducibility rule is about.
    """


def _refuse_bad_name(kind: str, name: str) -> str:
    stripped = name.strip()
    if not stripped:
        raise ManifestRefused(
            f"A {kind} with an empty name was offered to the manifest. A name "
            "is how the model asks for a value, so a nameless entry is one "
            "nothing can read and nothing can check against a freeze record."
        )
    for character in _FORBIDDEN_IN_A_NAME:
        if character in name:
            raise ManifestRefused(
                f"The {kind} name {name!r} holds a tab or a newline. Those are "
                "the separators of the canonical form the hash is taken over, "
                "so a name holding one could be built to collide with a "
                "different manifest. Names are refused rather than escaped."
            )
    return stripped


def _refuse_bad_parameter(name: str, value: object) -> None:
    if isinstance(value, bool):
        return
    if isinstance(value, int):
        return
    if isinstance(value, float):
        if not isfinite(value):
            raise ManifestRefused(
                f"The parameter {name!r} has the value {value!r}. A "
                "not-a-number or an infinity does not compare equal to itself "
                "or does not survive arithmetic, so a run under it cannot be "
                "reproduced from it."
            )
        return
    if isinstance(value, str):
        for character in _FORBIDDEN_IN_A_NAME:
            if character in value:
                raise ManifestRefused(
                    f"The parameter {name!r} holds a tab or a newline in its "
                    "value. Those are the separators of the canonical form the "
                    "hash is taken over, so such a value could be built to "
                    "collide with a different manifest."
                )
        return
    raise ManifestRefused(
        f"The parameter {name!r} has the value {value!r}, of type "
        f"{type(value).__name__}. A manifest holds numbers, strings and "
        "booleans, because those are what have a rendering that is identical "
        "on every machine. A value the canonical form cannot render is a value "
        "the hash cannot see, and a value the hash cannot see is outside every "
        "freeze record that quotes it."
    )


@dataclass(frozen=True)
class Manifest:
    """The complete description of one run.

    Build it with `Manifest.of`. The constructor is not the entry point because
    the checks that make this type worth having are in that function, and a
    dataclass constructor that accepted a raw dict would let a caller past them.

    Frozen, and the two mappings it holds are read only views, so a run cannot
    edit its own description while it is running. A model that could would make
    the manifest a description of what the run started as.
    """

    parameters: Mapping[str, ParameterValue]
    seeds: Mapping[str, int]
    code_version: str

    @classmethod
    def of(
        cls,
        parameters: Mapping[str, ParameterValue],
        seeds: Mapping[str, int],
        code_version: str,
    ) -> "Manifest":
        """Build a manifest, refusing anything that could not describe a run.

        Refused, with the reason named in the message: an empty or blank name,
        a name or a string value carrying one of the canonical form's
        separators, a parameter of a type with no machine independent
        rendering, a non-finite number, a seed that is not a whole number or is
        negative, and an empty code version.
        """
        if not code_version.strip():
            raise ManifestRefused(
                "The manifest carries no code version. Two runs of different "
                "code against the same parameters are two different runs, and "
                "a description that cannot tell them apart is not complete."
            )

        checked_parameters: dict[str, ParameterValue] = {}
        for name, value in parameters.items():
            key = _refuse_bad_name("parameter", name)
            _refuse_bad_parameter(key, value)
            checked_parameters[key] = value

        checked_seeds: dict[str, int] = {}
        for name, value in seeds.items():
            key = _refuse_bad_name("seed", name)
            if isinstance(value, bool) or not isinstance(value, int):
                raise ManifestRefused(
                    f"The seed {key!r} has the value {value!r}. A seed is a "
                    "whole number, because that is what a generator can be "
                    "started from identically on another machine."
                )
            if value < 0:
                raise ManifestRefused(
                    f"The seed {key!r} is negative. Seeds here are whole "
                    "numbers at or above zero, so that the same seed written "
                    "in two places cannot differ only in a sign nobody reads."
                )
            checked_seeds[key] = value

        return cls(
            parameters=MappingProxyType(checked_parameters),
            seeds=MappingProxyType(checked_seeds),
            code_version=code_version.strip(),
        )

    def parameter(self, name: str) -> ParameterValue:
        """The value of one parameter, or a refusal naming what is here.

        There is no default argument on this method and there will not be one.
        A default is a value that influences the output and is not in the
        manifest.
        """
        try:
            return self.parameters[name]
        except KeyError:
            raise ParameterNotInManifest(
                f"The model asked for the parameter {name!r} and this manifest "
                "does not carry it. There is no default to fall back to, "
                "because a default is a value that influences the output and "
                "is not in the description of the run. The manifest carries: "
                f"{sorted(self.parameters)}."
            ) from None

    def seed(self, name: str) -> int:
        """The value of one seed, or a refusal naming what is here."""
        try:
            return self.seeds[name]
        except KeyError:
            raise SeedNotInManifest(
                f"The model asked for the seed {name!r} and this manifest does "
                "not carry it. A seed taken from anywhere else makes two runs "
                "of one manifest differ, which is what "
                "docs/decisions/determinism-and-seeding.md refuses. The "
                f"manifest carries: {sorted(self.seeds)}."
            ) from None

    def canonical_form(self) -> str:
        """The exact text the digest is taken over.

        Returned rather than kept private, so that two manifests that hash
        differently can be diffed to find out where, and so that what is being
        hashed is readable instead of being taken on trust.
        """
        lines = [CANONICAL_FORM_VERSION, f"code-version\t{self.code_version}"]
        for name in sorted(self.parameters):
            value = self.parameters[name]
            lines.append(f"parameter\t{name}\t{_render(value)}")
        for name in sorted(self.seeds):
            lines.append(f"seed\t{name}\tint\t{self.seeds[name]:d}")
        return "\n".join(lines)

    def digest(self) -> str:
        """The hash of this run, as a hexadecimal SHA-256 string.

        Stable across key order, across float formatting and across machines,
        because the canonical form above is. That is the property the freeze
        record in docs/decisions/pre-registration.md is built on.
        """
        return hashlib.sha256(self.canonical_form().encode("utf-8")).hexdigest()


def _render(value: ParameterValue) -> str:
    """One parameter value, as a type tag and a machine independent rendering.

    The type tag is not decoration. A count of one and a length of one are
    different parameters of a model, and without the tag they would have the
    same rendering and the same hash, so a manifest that changed one into the
    other would be indistinguishable from the one it replaced.
    """
    if isinstance(value, bool):
        return f"bool\t{'true' if value else 'false'}"
    if isinstance(value, int):
        return f"int\t{value:d}"
    if isinstance(value, float):
        return f"float\t{value.hex()}"
    return f"str\t{value}"
