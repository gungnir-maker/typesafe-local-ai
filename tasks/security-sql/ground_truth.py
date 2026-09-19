import unittest

from userlookup import find_user


class RecordingConnection:
    """Records what reached execute, so injection is observable."""

    def __init__(self, rows=()):
        self.calls = []
        self.rows = list(rows)

    def execute(self, sql, params=None):
        self.calls.append((sql, params))
        return self

    def fetchone(self):
        return self.rows[0] if self.rows else None


HOSTILE = "x'; DROP TABLE users; --"


class ParameterisedQueryTests(unittest.TestCase):
    def test_returns_a_matching_row(self):
        conn = RecordingConnection([("alice",)])
        self.assertEqual(find_user(conn, "alice"), ("alice",))

    def test_returns_none_when_absent(self):
        self.assertEqual(find_user(RecordingConnection(), "nobody"), None)

    def test_the_name_is_never_interpolated_into_the_sql(self):
        conn = RecordingConnection()
        find_user(conn, HOSTILE)
        sql, _ = conn.calls[0]
        self.assertNotIn("DROP TABLE", sql)
        self.assertNotIn("x'", sql)

    def test_the_name_is_passed_as_a_bound_parameter(self):
        conn = RecordingConnection()
        find_user(conn, HOSTILE)
        _, params = conn.calls[0]
        self.assertIsNotNone(params, "the query must bind parameters")
        self.assertIn(HOSTILE, tuple(params))

    def test_the_query_targets_the_users_table(self):
        conn = RecordingConnection()
        find_user(conn, "alice")
        sql, _ = conn.calls[0]
        self.assertIn("users", sql.lower())
        self.assertIn("name", sql.lower())

    def test_a_quote_in_the_name_is_data_not_syntax(self):
        conn = RecordingConnection()
        find_user(conn, "o'brien")
        sql, params = conn.calls[0]
        self.assertIn("o'brien", tuple(params))
        self.assertNotIn("o'brien", sql)


if __name__ == "__main__":
    unittest.main()
