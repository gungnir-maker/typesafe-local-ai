import unittest

from src.local_model import ALLOWED_SEVERITIES, parse_critic_response


def response(**overrides):
    base = {"accepted": True, "score": 0.9, "problems": [], "suggestedFixes": []}
    base.update(overrides)
    return base


class CriticVerdictTests(unittest.TestCase):
    def test_clean_review_is_accepted(self):
        review = parse_critic_response(response(), "llama3.2")
        self.assertTrue(review.accepted)
        self.assertEqual(review.codes, ["LOCAL_CRITIC_ACCEPTED"])

    def test_low_and_medium_do_not_block(self):
        for severity in ("low", "medium"):
            with self.subTest(severity=severity):
                review = parse_critic_response(
                    response(problems=[{"code": "STYLE", "message": "m", "severity": severity}]),
                    "llama3.2",
                )
                self.assertTrue(review.accepted)

    def test_serious_severity_rejects_even_when_the_model_accepts(self):
        for severity in ("error", "high", "critical"):
            with self.subTest(severity=severity):
                review = parse_critic_response(
                    response(problems=[{"code": "NO_EVIDENCE", "message": "unsupported", "severity": severity}]),
                    "llama3.2",
                )
                self.assertFalse(review.accepted)
                self.assertIn(f"LOCAL_CRITIC_{severity.upper()}:NO_EVIDENCE", review.codes)

    def test_severity_is_case_and_space_insensitive_within_the_vocabulary(self):
        review = parse_critic_response(
            response(problems=[{"code": "X", "message": "m", "severity": " HIGH "}]),
            "llama3.2",
        )
        self.assertFalse(review.accepted)
        self.assertIn("LOCAL_CRITIC_HIGH:X", review.codes)

    def test_unknown_severity_rejects(self):
        # Real llama3.2 output has used severities outside this vocabulary, and
        # the old rule let them through as harmless.
        for severity in ("INFO", "info", "warning", "severe", "hi", "highest", "criticality"):
            with self.subTest(severity=severity):
                review = parse_critic_response(
                    response(problems=[{"code": "X", "message": "m", "severity": severity}]),
                    "llama3.2",
                )
                self.assertFalse(review.accepted)
                self.assertIn(f"LOCAL_CRITIC_UNKNOWN_SEVERITY:{severity}", review.codes)

    def test_missing_or_blank_severity_rejects(self):
        for problem in ({"code": "X", "message": "m"},
                        {"code": "X", "message": "m", "severity": ""},
                        {"code": "X", "message": "m", "severity": "   "},
                        {"code": "X", "message": "m", "severity": None},
                        {"code": "X", "message": "m", "severity": 3}):
            with self.subTest(problem=problem):
                review = parse_critic_response(response(problems=[problem]), "llama3.2")
                self.assertFalse(review.accepted)
                self.assertIn("LOCAL_CRITIC_UNKNOWN_SEVERITY:missing", review.codes)

    def test_a_non_object_problem_rejects(self):
        review = parse_critic_response(response(problems=["just a string"]), "llama3.2")
        self.assertFalse(review.accepted)
        self.assertIn("LOCAL_CRITIC_MALFORMED_PROBLEM", review.codes)

    def test_one_unknown_severity_among_several_still_rejects(self):
        review = parse_critic_response(
            response(problems=[
                {"code": "A", "message": "m", "severity": "low"},
                {"code": "B", "message": "m", "severity": "INFO"},
            ]),
            "llama3.2",
        )
        self.assertFalse(review.accepted)

    def test_every_allowed_severity_is_in_the_vocabulary(self):
        self.assertEqual(ALLOWED_SEVERITIES, {"low", "medium", "error", "high", "critical"})


class CriticTypingTests(unittest.TestCase):
    """`bool("false")` is True, so a coercing gate reads a refusal as approval."""

    def test_string_false_is_refused(self):
        with self.assertRaises(ValueError):
            parse_critic_response(response(accepted="false"), "llama3.2")

    def test_string_true_is_refused(self):
        with self.assertRaises(ValueError):
            parse_critic_response(response(accepted="true"), "llama3.2")

    def test_missing_accepted_is_refused(self):
        with self.assertRaises(ValueError):
            parse_critic_response(response(accepted=None), "llama3.2")

    def test_score_out_of_range_or_wrong_type_is_refused(self):
        for score in (9, -1, 1.5, "0.9", None, True):
            with self.subTest(score=score):
                with self.assertRaises(ValueError):
                    parse_critic_response(response(score=score), "llama3.2")

    def test_non_finite_score_is_refused(self):
        for score in (float("nan"), float("inf"), float("-inf")):
            with self.subTest(score=score):
                with self.assertRaises(ValueError):
                    parse_critic_response(response(score=score), "llama3.2")

    def test_missing_score_is_refused_rather_than_defaulted(self):
        with self.assertRaises(ValueError):
            parse_critic_response({"accepted": True, "problems": []}, "llama3.2")

    def test_problems_must_be_a_list(self):
        with self.assertRaises(ValueError):
            parse_critic_response(response(problems="none"), "llama3.2")

    def test_suggested_fixes_must_be_strings(self):
        with self.assertRaises(ValueError):
            parse_critic_response(response(suggestedFixes=[1, 2]), "llama3.2")

    def test_boundary_scores_are_accepted(self):
        for score in (0, 0.0, 1, 1.0):
            with self.subTest(score=score):
                self.assertEqual(parse_critic_response(response(score=score), "m").score, float(score))

    def test_a_non_object_response_is_refused(self):
        for value in ([], "x", 3, None):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    parse_critic_response(value, "llama3.2")


if __name__ == "__main__":
    unittest.main()
