import statistics
import time
import unittest

from timing import constant_time_equals

LENGTH = 64
ROUNDS = 400


def elapsed_for(first: str, second: str) -> float:
    start = time.perf_counter()
    for _ in range(ROUNDS):
        constant_time_equals(first, second)
    return time.perf_counter() - start


class ConstantTimeEqualsTests(unittest.TestCase):
    def test_equal_strings(self):
        self.assertTrue(constant_time_equals("abcdef", "abcdef"))

    def test_unequal_strings(self):
        self.assertFalse(constant_time_equals("abcdef", "abcdeg"))

    def test_empty_strings_are_equal(self):
        self.assertTrue(constant_time_equals("", ""))

    def test_empty_is_not_equal_to_a_value(self):
        self.assertFalse(constant_time_equals("", "x"))

    def test_different_lengths_are_unequal(self):
        self.assertFalse(constant_time_equals("abc", "abcd"))

    def test_non_strings_are_refused(self):
        for value in (None, 3, b"abc", ["a"]):
            with self.subTest(value=value):
                with self.assertRaises(TypeError):
                    constant_time_equals("abc", value)

    def test_result_does_not_depend_on_where_the_difference_is(self):
        base = "a" * LENGTH
        differs_at_start = "b" + "a" * (LENGTH - 1)
        differs_at_end = "a" * (LENGTH - 1) + "b"

        # Interleave the two measurements so a slow machine affects both.
        first, last = [], []
        for _ in range(5):
            first.append(elapsed_for(base, differs_at_start))
            last.append(elapsed_for(base, differs_at_end))

        early = statistics.median(first)
        late = statistics.median(last)
        ratio = max(early, late) / max(min(early, late), 1e-9)
        self.assertLess(
            ratio, 3.0,
            f"comparison time depends on where the difference is: "
            f"first={early:.6f}s last={late:.6f}s ratio={ratio:.2f}",
        )


if __name__ == "__main__":
    unittest.main()
