import unittest

from src.local_model import parse_critic_response


def response(**overrides):
    base = {"accepted": True, "score": 0.9, "problems": [], "suggestedFixes": []}
    base.update(overrides)
    return base


class CriticVerdictTests(unittest.TestCase):
    def test_clean_review_is_accepted(self):
        review = parse_critic_response(response(), "llama3.2")
        self.assertTrue(review.accepted)
        self.assertEqual(review.codes, ["LOCAL_CRITIC_ACCEPTED"])

    def test_low_severity_problem_does_not_block_acceptance(self):
        review = parse_critic_response(
            response(problems=[{"code": "STYLE", "message": "prefer a helper", "severity": "low"}]),
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

    def test_unknown_severity_spelling_does_not_block_acceptance(self):
        # Real llama3.2 output has used severities outside the serious set.
        review = parse_critic_response(
            response(problems=[{"code": "X", "message": "m", "severity": "INFO"}]),
            "llama3.2",
        )
        self.assertTrue(review.accepted)

    def test_missing_score_is_an_error_not_a_zero_score_pass(self):
        with self.assertRaises(KeyError):
            parse_critic_response({"accepted": True, "problems": []}, "llama3.2")


if __name__ == "__main__":
    unittest.main()
