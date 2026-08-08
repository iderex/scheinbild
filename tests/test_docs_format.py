"""The document checker's own proof that it refuses what it names.

Each rule has a case that trips it and a neighbouring case that does not, and
the neighbour is the near miss rather than something that could never have
failed. A checker with only positive cases proves it can say no, not that it
says no to the right thing.

Every case here is bytes written in the test. Nothing reads the repository's own
documents to decide a rule, because a case built out of the tree proves the
state of the tree on the day it ran and not the guard.
"""

import unittest

from tools.docs_format import inspect, repair


def rules(defects):
    """The rule names a run produced, in order, so a case can assert the set."""
    return [defect.rule for defect in defects]


class TheCarriageReturnIsRefused(unittest.TestCase):
    def test_a_stored_carriage_return_is_a_defect(self):
        found = inspect("d.md", b"one\r\ntwo\n")
        self.assertEqual(rules(found), ["carriage-return"])

    def test_the_same_document_without_it_is_clean(self):
        self.assertEqual(inspect("d.md", b"one\ntwo\n"), [])

    def test_the_defect_names_the_line_it_is_on(self):
        found = inspect("d.md", b"one\ntwo\r\nthree\n")
        self.assertEqual(found[0].line, 2)

    def test_a_lone_carriage_return_is_refused_too(self):
        # The near miss. A file converted by a tool that wrote CR without LF
        # has no CRLF pair in it at all, and a check looking for the pair
        # passes it.
        found = inspect("d.md", b"one\rtwo\n")
        self.assertEqual(rules(found), ["carriage-return"])


class TrailingWhitespaceIsRefused(unittest.TestCase):
    def test_a_line_ending_in_a_space_is_a_defect(self):
        found = inspect("d.md", b"one \ntwo\n")
        self.assertEqual(rules(found), ["trailing-whitespace"])

    def test_a_line_with_the_space_in_the_middle_is_clean(self):
        self.assertEqual(inspect("d.md", b"one two\n"), [])

    def test_the_empty_line_after_the_final_newline_is_not_a_defect(self):
        # The near miss this rule most easily gets wrong. Splitting on the line
        # feed leaves an empty last element for a file that ends correctly, and
        # a rule that strips it reports every well-formed document in the tree.
        self.assertEqual(inspect("d.md", b"one\n\ntwo\n"), [])

    def test_a_crlf_line_is_reported_once_and_not_twice(self):
        # The near miss between two rules rather than inside one. Splitting on
        # the line feed leaves the carriage return at the end of the line, so a
        # whitespace rule that reads the raw line reports every CRLF line twice
        # and sends the reader looking for a space that is not there.
        found = inspect("d.md", b"one\r\ntwo\n")
        self.assertEqual(rules(found), ["carriage-return"])

    def test_a_line_with_both_is_reported_under_both(self):
        found = inspect("d.md", b"one \r\ntwo\n")
        self.assertEqual(
            sorted(rules(found)), ["carriage-return", "trailing-whitespace"]
        )

    def test_a_blank_line_carrying_a_space_is_a_defect(self):
        found = inspect("d.md", b"one\n \ntwo\n")
        self.assertEqual(rules(found), ["trailing-whitespace"])
        self.assertEqual(found[0].line, 2)


class TheFinalNewlineIsRequired(unittest.TestCase):
    def test_a_file_not_ending_in_a_newline_is_a_defect(self):
        found = inspect("d.md", b"one\ntwo")
        self.assertEqual(rules(found), ["no-final-newline"])

    def test_the_same_file_with_one_is_clean(self):
        self.assertEqual(inspect("d.md", b"one\ntwo\n"), [])

    def test_an_empty_file_is_not_reported(self):
        # A document with no bytes has no last line to be missing a newline
        # after, and reporting one would be a rule about a file that says
        # nothing.
        self.assertEqual(inspect("d.md", b""), [])


class TheHardTabIsRefused(unittest.TestCase):
    def test_a_tab_is_a_defect(self):
        found = inspect("d.md", b"one\n\tindented\n")
        self.assertEqual(rules(found), ["hard-tab"])

    def test_spaces_in_the_same_position_are_clean(self):
        self.assertEqual(inspect("d.md", b"one\n    indented\n"), [])


class TheRepairIsTheOneTheMessageNames(unittest.TestCase):
    """What --fix does, and the one defect it deliberately leaves alone."""

    def test_it_repairs_the_three_it_claims(self):
        broken = b"one \r\n\ttwo  \r\nthree"
        self.assertEqual(repair(broken), b"one\n\ttwo\nthree\n")

    def test_a_repaired_document_passes_the_check_apart_from_the_tab(self):
        broken = b"one \r\ntwo  \r\nthree"
        self.assertEqual(inspect("d.md", repair(broken)), [])

    def test_the_tab_survives_the_repair(self):
        # Stated as a test rather than as a sentence, because "the fix does not
        # fix this one" is the kind of claim that quietly stops being true.
        repaired = repair(b"\tone\n")
        self.assertEqual(rules(inspect("d.md", repaired)), ["hard-tab"])

    def test_a_clean_document_is_returned_unchanged(self):
        clean = b"one\ntwo\n"
        self.assertEqual(repair(clean), clean)


if __name__ == "__main__":
    unittest.main()
