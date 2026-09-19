import unittest

from envelope import envelope


class EnvelopeTests(unittest.TestCase):
    def test_shape(self):
        body = envelope([1, 2], 1, 2, 5)
        self.assertEqual(set(body), {"data", "meta", "links"})
        self.assertEqual(set(body["meta"]), {"page", "size", "total", "pages"})
        self.assertEqual(set(body["links"]), {"self", "next", "prev"})

    def test_data_is_passed_through(self):
        items = [{"id": 1}]
        self.assertEqual(envelope(items, 1, 10, 1)["data"], items)

    def test_meta_values(self):
        body = envelope([], 2, 20, 135)
        self.assertEqual(body["meta"], {"page": 2, "size": 20, "total": 135, "pages": 7})

    def test_pages_rounds_up(self):
        self.assertEqual(envelope([], 1, 20, 21)["meta"]["pages"], 2)

    def test_pages_is_zero_when_empty(self):
        self.assertEqual(envelope([], 1, 20, 0)["meta"]["pages"], 0)

    def test_first_page_has_no_prev(self):
        self.assertIsNone(envelope([], 1, 20, 100)["links"]["prev"])

    def test_last_page_has_no_next(self):
        self.assertIsNone(envelope([], 7, 20, 135)["links"]["next"])

    def test_middle_page_has_both_links(self):
        links = envelope([], 2, 20, 100)["links"]
        self.assertEqual(links["prev"], "/items?page=1&size=20")
        self.assertEqual(links["next"], "/items?page=3&size=20")

    def test_self_link(self):
        self.assertEqual(envelope([], 3, 10, 100)["links"]["self"], "/items?page=3&size=10")

    def test_rejects_bad_size(self):
        for size in (0, -1):
            with self.subTest(size=size):
                with self.assertRaises(ValueError):
                    envelope([], 1, size, 10)

    def test_rejects_bad_total(self):
        with self.assertRaises(ValueError):
            envelope([], 1, 10, -1)

    def test_rejects_bad_page(self):
        with self.assertRaises(ValueError):
            envelope([], 0, 10, 10)


if __name__ == "__main__":
    unittest.main()
