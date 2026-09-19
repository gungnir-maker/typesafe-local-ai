import json
import os
import unittest
import urllib.error

from src.typesafe_judge import CHECK_ID, DEFAULT_THRESHOLD, judge_claim, resolve_api_key


class FakeResponse:
    def __init__(self, payload):
        self._body = json.dumps(payload).encode()

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def requester(payload=None, error=None, seen=None):
    def call(request, timeout=None):
        if seen is not None:
            seen.append(json.loads(request.data))
        if error is not None:
            raise error
        return FakeResponse(payload)
    return call


def answer(noul, model="jev-1.13.0"):
    return {"model": model, "answers": {CHECK_ID: {"type": "noul", "noul": noul}}}


CLAIM = {"taskId": "t", "task": "do a thing", "status": "done", "summary": "did it",
         "changedFiles": ["src/a.py"], "testsClaimed": ["pytest"], "blockers": []}


class JudgeScoreTests(unittest.TestCase):
    def judge(self, **kwargs):
        kwargs.setdefault("api_key", "k")
        return judge_claim("do a thing", CLAIM, [{"command": "pytest", "passed": True}], **kwargs)

    def test_score_above_threshold_passes(self):
        result = self.judge(requester=requester(answer(0.63)))
        self.assertTrue(result.passed)
        self.assertAlmostEqual(result.score, 0.63)
        self.assertEqual(result.model, "jev-1.13.0")
        self.assertEqual(result.codes, ["SEMANTIC_CHECK_PASSED"])

    def test_score_below_threshold_fails(self):
        result = self.judge(requester=requester(answer(0.32)))
        self.assertFalse(result.passed)
        self.assertEqual(result.codes, ["SEMANTIC_CHECK_FAILED"])

    def test_score_exactly_at_threshold_passes(self):
        result = self.judge(requester=requester(answer(DEFAULT_THRESHOLD)))
        self.assertTrue(result.passed)

    def test_out_of_range_score_is_invalid_not_a_pass(self):
        result = self.judge(requester=requester(answer(9)))
        self.assertFalse(result.passed)
        self.assertIsNone(result.score)
        self.assertEqual(result.codes, ["SEMANTIC_RESPONSE_INVALID"])

    def test_non_numeric_score_is_invalid(self):
        result = self.judge(requester=requester(answer("0.9")))
        self.assertFalse(result.passed)
        self.assertEqual(result.codes, ["SEMANTIC_RESPONSE_INVALID"])

    def test_missing_answer_is_invalid(self):
        result = self.judge(requester=requester({"model": "x", "answers": {}}))
        self.assertFalse(result.passed)
        self.assertEqual(result.codes, ["SEMANTIC_RESPONSE_INVALID"])

    def test_http_error_is_unavailable_and_named(self):
        error = urllib.error.HTTPError("u", 401, "unauthorized", {}, None)
        result = self.judge(requester=requester(error=error))
        self.assertFalse(result.passed)
        self.assertEqual(result.codes, ["TYPESAFE_UNAVAILABLE:HTTP_401"])

    def test_transport_error_is_unavailable(self):
        result = self.judge(requester=requester(error=urllib.error.URLError("down")))
        self.assertFalse(result.passed)
        self.assertEqual(result.codes, ["TYPESAFE_UNAVAILABLE"])

    def test_no_key_is_unavailable_without_a_request(self):
        seen = []
        result = judge_claim("do a thing", CLAIM, api_key="", requester=requester(answer(0.9), seen=seen))
        self.assertFalse(result.passed)
        self.assertEqual(result.codes, ["TYPESAFE_UNAVAILABLE"])
        self.assertEqual(seen, [])

    def test_request_matches_the_adapter_shape(self):
        seen = []
        self.judge(requester=requester(answer(0.7), seen=seen))
        body = seen[0]
        self.assertEqual(body["model"], "jev-latest")
        self.assertEqual(list(body["questions"]), [CHECK_ID])
        self.assertEqual(body["questions"][CHECK_ID]["type"], "noul")
        # `state` is a JSON *string*, not a nested object.
        state = json.loads(body["state"])
        self.assertEqual(state["task"], "do a thing")
        self.assertEqual(state["result"]["taskId"], "t")
        self.assertEqual(state["tests"][0]["command"], "pytest")


class KeyResolutionTests(unittest.TestCase):
    def test_environment_wins(self):
        os.environ["TYPESAFE_TEST_KEY"] = "from-env"
        try:
            self.assertEqual(resolve_api_key("TYPESAFE_TEST_KEY"), "from-env")
        finally:
            del os.environ["TYPESAFE_TEST_KEY"]

    def test_blank_environment_value_is_not_a_key(self):
        os.environ["TYPESAFE_TEST_KEY"] = "   "
        try:
            self.assertIsNone(resolve_api_key("TYPESAFE_TEST_KEY"))
        finally:
            del os.environ["TYPESAFE_TEST_KEY"]

    def test_unknown_reference_returns_none_without_raising(self):
        self.assertIsNone(resolve_api_key("TYPESAFE_DEFINITELY_ABSENT_KEY"))


if __name__ == "__main__":
    unittest.main()
