import unittest

from errors import error_body


class ErrorBodyTests(unittest.TestCase):
    def test_empty_input(self):
        self.assertEqual(error_body([]), {"errors": []})

    def test_full_error(self):
        body = error_body([{"field": "email", "code": "required", "message": "Email is required."}])
        self.assertEqual(body, {"errors": [
            {"field": "email", "code": "required", "message": "Email is required."}
        ]})

    def test_defaults(self):
        self.assertEqual(error_body([{}]), {"errors": [
            {"field": "base", "code": "invalid", "message": "Invalid value."}
        ]})

    def test_every_error_has_exactly_three_keys(self):
        body = error_body([{"field": "a"}, {"code": "c"}, {"message": "m"}, {}])
        for entry in body["errors"]:
            self.assertEqual(set(entry), {"field", "code", "message"})

    def test_order_is_preserved(self):
        body = error_body([{"field": "b"}, {"field": "a"}])
        self.assertEqual([e["field"] for e in body["errors"]], ["b", "a"])

    def test_field_is_lowercased_and_stripped(self):
        self.assertEqual(error_body([{"field": "  Email  "}])["errors"][0]["field"], "email")

    def test_non_string_values_are_refused(self):
        for key in ("field", "code", "message"):
            with self.subTest(key=key):
                with self.assertRaises(ValueError):
                    error_body([{key: 3}])

    def test_non_dict_error_is_refused(self):
        for value in ("boom", 3, None, ["a"]):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    error_body([value])

    def test_input_is_not_modified(self):
        original = [{"field": "Email"}]
        snapshot = [dict(entry) for entry in original]
        error_body(original)
        self.assertEqual(original, snapshot)


if __name__ == "__main__":
    unittest.main()
