"""v3.8 naming the codebase a map describes, with the standard that already exists.

`purl` (package-url, ECMA-427, what SPDX uses) names a repository independently of where
anyone checked it out. This is the subset the frame needs — the full implementation is
`packageurl-python`, kept out because `lib/` is stdlib-only.

Each test is the executable spec of one C-15.* clause in features/contract-layer/contract.md.
"""
from __future__ import annotations

import pytest

from lib.purl import PurlError, identity, parse, render, same_subject


def test_a_codebase_is_named_by_package_url_not_by_a_path():
    """C-15.1 - a path says where somebody checked something out, which is exactly what must
    not matter; the purl says what the thing IS."""
    assert parse("pkg:github/divnjl2/nexus-athena@bae35c6") == {
        "type": "github", "namespace": "divnjl2", "name": "nexus-athena", "version": "bae35c6"}
    assert parse("pkg:generic/internal-service") == {
        "type": "generic", "namespace": "", "name": "internal-service", "version": ""}
    assert parse("pkg:golang/github.com/org/mod/sub@v1.2.3")["namespace"] == "github.com/org/mod"
    assert render(parse("pkg:GitHub/a/b@1")) == "pkg:github/a/b@1"

    for bad in ("", "github/a/b", "pkg:", "pkg:github/", "https://github.com/a/b"):
        with pytest.raises(PurlError, match="refused"):
            parse(bad)


def test_the_same_codebase_at_two_commits_is_the_same_subject():
    """C-15.2 - version is dropped on purpose: the per-clause digests already answer whether
    the CODE moved, and comparing versions here would make every commit a new project."""
    assert identity("pkg:github/a/b@sha1") == "pkg:github/a/b"
    assert same_subject("pkg:github/a/b@sha1", "pkg:github/a/b@sha2")
    assert not same_subject("pkg:github/a/b", "pkg:github/a/c")
    assert not same_subject("pkg:github/a/b", "pkg:pypi/b")


def test_an_unnamed_subject_is_not_agreement():
    """C-15.3 - silence is not proof here either: an absent subject on either side is
    reported as "not the same", and the caller decides whether that is an error."""
    assert not same_subject("", "pkg:github/a/b")
    assert not same_subject("pkg:github/a/b", "")
    assert not same_subject("", "")
    assert not same_subject("pkg:github/a/b", "not-a-purl"), "a malformed side never matches"
