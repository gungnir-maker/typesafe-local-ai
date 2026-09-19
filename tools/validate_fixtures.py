"""Throwaway validator: every fixture must be satisfiable by the right answer.

A task whose hidden test fails against a correct solution would blame the model
for the benchmark's bug, and every such failure would look like a model
weakness. This checks the other direction from "the starter fails": that a
known-good solution passes.
"""

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.loop import load_tasks  # noqa: E402

REFERENCE = {
    "python-slugify": {"textlib.py": '''import re


def slugify(text: str) -> str:
    """Return a URL-safe slug of text."""
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
'''},
    "python-duration": {"durations.py": '''import re

PATTERN = re.compile(r"^(?:(\\d+)h)?(?:(\\d+)m)?(?:(\\d+)s)?$")


def parse_duration(text: str) -> int:
    """Parse a duration such as ``1h30m`` into seconds."""
    if not isinstance(text, str) or not text:
        raise ValueError("empty duration")
    match = PATTERN.match(text)
    if match is None or not any(match.groups()):
        raise ValueError(f"bad duration: {text!r}")
    hours, minutes, seconds = (int(part) if part else 0 for part in match.groups())
    return hours * 3600 + minutes * 60 + seconds
'''},
    "python-chunk": {"chunks.py": '''def chunk(items, size):
    """Split items into lists of at most ``size`` items."""
    if size <= 0:
        raise ValueError("size must be positive")
    return [list(items[i:i + size]) for i in range(0, len(items), size)]
'''},
    "python-roman": {"roman.py": '''VALUES = [
    (1000, "M"), (900, "CM"), (500, "D"), (400, "CD"), (100, "C"), (90, "XC"),
    (50, "L"), (40, "XL"), (10, "X"), (9, "IX"), (5, "V"), (4, "IV"), (1, "I"),
]


def int_to_roman(number: int) -> str:
    """Convert an integer to its Roman numeral."""
    if not isinstance(number, int) or isinstance(number, bool):
        raise ValueError("number must be an integer")
    if number < 1 or number > 3999:
        raise ValueError("number must be between 1 and 3999")
    out = []
    for value, symbol in VALUES:
        while number >= value:
            out.append(symbol)
            number -= value
    return "".join(out)
'''},
    "python-csvline": {"csvline.py": '''def parse_csv_line(line: str) -> list:
    """Split one CSV record into its fields."""
    fields, current, quoted, index = [], [], False, 0
    while index < len(line):
        char = line[index]
        if quoted:
            if char == '"':
                if index + 1 < len(line) and line[index + 1] == '"':
                    current.append('"')
                    index += 2
                    continue
                quoted = False
                index += 1
                continue
            current.append(char)
            index += 1
            continue
        if char == '"' and not current:
            quoted = True
            index += 1
            continue
        if char == ",":
            fields.append("".join(current))
            current = []
            index += 1
            continue
        current.append(char)
        index += 1
    fields.append("".join(current))
    return fields
'''},
    "security-safejoin": {"safejoin.py": '''import posixpath


def safe_join(base: str, user_path: str) -> str:
    """Join user_path onto base, refusing anything that escapes base."""
    if not isinstance(user_path, str) or not user_path.strip():
        raise ValueError("path must be a non-empty string")
    if posixpath.isabs(user_path):
        raise ValueError("path must be relative")
    base_norm = posixpath.normpath(base)
    joined = posixpath.normpath(posixpath.join(base_norm, user_path))
    if joined == base_norm or not joined.startswith(base_norm.rstrip("/") + "/"):
        raise ValueError("path escapes the base directory")
    return joined
'''},
    "security-html": {"htmlesc.py": '''def escape_html(text: str) -> str:
    """Escape text for HTML text content and quoted attributes."""
    if not isinstance(text, str):
        raise TypeError("text must be a string")
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#x27;")
    )
'''},
    "security-sql": {"userlookup.py": '''def find_user(conn, name):
    """Return the users row whose name matches, or None."""
    cursor = conn.execute("SELECT id, name FROM users WHERE name = ?", (name,))
    return cursor.fetchone()
'''},
    "security-timing": {"timing.py": '''def constant_time_equals(a: str, b: str) -> bool:
    """Compare two strings without leaking the first difference in time."""
    if not isinstance(a, str) or not isinstance(b, str):
        raise TypeError("both arguments must be strings")
    if len(a) != len(b):
        return False
    difference = 0
    for left, right in zip(a, b):
        difference |= ord(left) ^ ord(right)
    return difference == 0
'''},
    "bugfix-window": {"window.py": '''def last_n(items, n):
    """Return the last n items of items, in order."""
    if n < 0:
        raise ValueError("n must not be negative")
    if n == 0:
        return []
    return list(items[-n:])
'''},
    "bugfix-mutation": {"tags.py": '''def normalise_tags(tags):
    """Return the tags lowercased, de-duplicated and sorted."""
    return sorted({tag.lower() for tag in tags})
'''},
    "bugfix-default": {"tagevent.py": '''def add_tag(tag, tags=None):
    """Return the existing tags with tag appended."""
    return list(tags) + [tag] if tags else [tag]
'''},
    "bugfix-closure": {"closure.py": '''def make_formatters(prefixes):
    """Return one formatter function per prefix."""
    def build(prefix):
        def format_value(value):
            return prefix + ": " + value
        return format_value

    return [build(prefix) for prefix in prefixes]
'''},
    "jsonapi-paginate": {"pagination.py": '''def page_params(query, default_size, max_size):
    """Return (limit, offset) for the given query mapping."""
    def positive(value, field):
        if not isinstance(value, str) or not value.strip().isdigit() or int(value) < 1:
            raise ValueError(f"{field} must be a positive integer")
        return int(value)

    page = positive(query["page"], "page") if "page" in query else 1
    size = positive(query["size"], "size") if "size" in query else default_size
    size = min(size, max_size)
    return size, (page - 1) * size
'''},
    "jsonapi-envelope": {"envelope.py": '''import math


def envelope(items, page, size, total):
    """Build the response body for a paginated list endpoint."""
    if size <= 0:
        raise ValueError("size must be positive")
    if total < 0:
        raise ValueError("total must not be negative")
    if page < 1:
        raise ValueError("page must start at 1")

    pages = math.ceil(total / size) if total else 0

    def link(number):
        return f"/items?page={number}&size={size}"

    return {
        "data": items,
        "meta": {"page": page, "size": size, "total": total, "pages": pages},
        "links": {
            "self": link(page),
            "next": link(page + 1) if page < pages else None,
            "prev": link(page - 1) if page > 1 else None,
        },
    }
'''},
    "jsonapi-errors": {"errors.py": '''def error_body(errors):
    """Normalise validation failures into an error document."""
    out = []
    for entry in errors:
        if not isinstance(entry, dict):
            raise ValueError("each error must be an object")
        field = entry.get("field", "base")
        code = entry.get("code", "invalid")
        message = entry.get("message", "Invalid value.")
        for value in (field, code, message):
            if not isinstance(value, str):
                raise ValueError("field, code and message must be strings")
        out.append({"field": field.strip().lower(), "code": code, "message": message})
    return {"errors": out}
'''},
    "docs-threshold": {"README.md": '''# Retry policy

Requests are retried automatically when the upstream returns a 5xx response.

The current limit is `MAX_RETRIES = 3`.

Retries use exponential backoff starting at 200ms.
'''},
    "docs-docstring": {"mathx.py": '''"""Arithmetic helpers."""


def divide(a: float, b: float) -> float:
    """Divide a by b and return the quotient.

    Raises:
        ValueError: if b is zero.
    """
    if b == 0:
        raise ValueError("cannot divide by zero")
    return a / b
'''},
    "docs-changelog": {"CHANGELOG.md": '''# Changelog

All notable changes to this project are documented here.

## Unreleased

### Changed

- The default request timeout increased from 10 seconds to 30 seconds.

## 1.2.0

### Added

- Retry support for upstream 5xx responses.

### Fixed

- Backoff no longer grows without bound.
'''},
    "js-clamp": {"range.js": ''''use strict';

function clamp(value, min, max) {
  if (typeof value !== 'number' || !Number.isFinite(value)) throw new TypeError('value');
  if (typeof min !== 'number' || !Number.isFinite(min)) throw new TypeError('min');
  if (typeof max !== 'number' || !Number.isFinite(max)) throw new TypeError('max');
  if (min > max) throw new RangeError('min must not exceed max');
  return Math.min(Math.max(value, min), max);
}

module.exports = { clamp };
'''},
    "js-chunk": {"chunk.js": ''''use strict';

function chunkArray(items, size) {
  if (!Array.isArray(items)) throw new TypeError('items must be an array');
  if (typeof size !== 'number' || !Number.isInteger(size) || size <= 0) {
    throw new RangeError('size must be a positive integer');
  }
  const out = [];
  for (let i = 0; i < items.length; i += size) out.push(items.slice(i, i + size));
  return out;
}

module.exports = { chunkArray };
'''},
    "js-query": {"querystring.js": ''''use strict';

function parseQueryString(query) {
  const out = {};
  const text = query.startsWith('?') ? query.slice(1) : query;
  if (text === '') return out;
  for (const segment of text.split('&')) {
    if (segment === '') continue;
    const index = segment.indexOf('=');
    const rawKey = index === -1 ? segment : segment.slice(0, index);
    const rawValue = index === -1 ? '' : segment.slice(index + 1);
    const key = decodeURIComponent(rawKey.replace(/\\+/g, ' '));
    const value = decodeURIComponent(rawValue.replace(/\\+/g, ' '));
    if (Object.prototype.hasOwnProperty.call(out, key)) {
      out[key] = Array.isArray(out[key]) ? [...out[key], value] : [out[key], value];
    } else {
      out[key] = value;
    }
  }
  return out;
}

module.exports = { parseQueryString };
'''},
    "js-slug": {"slug.js": ''''use strict';

function slugify(text, maxLength) {
  if (typeof text !== 'string') throw new TypeError('text must be a string');
  if (!Number.isInteger(maxLength) || maxLength < 0) {
    throw new RangeError('maxLength must be a non-negative integer');
  }
  const slug = text.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '');
  return slug.slice(0, maxLength).replace(/-+$/g, '');
}

module.exports = { slugify };
'''},
}


def run(task, files):
    work = Path(tempfile.mkdtemp())
    shutil.copytree(task.starter, work, dirs_exist_ok=True)
    for name, content in files.items():
        path = work / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
    shutil.copy(task.ground_truth, work / task.ground_truth_name)
    result = subprocess.run(task.test_command, shell=True, cwd=work, capture_output=True, text=True)
    shutil.rmtree(work)
    return result.returncode == 0, (result.stdout + result.stderr)


def main() -> int:
    problems = []
    tasks = load_tasks(Path(__file__).resolve().parent.parent / "tasks")
    for task in tasks:
        files = REFERENCE.get(task.id)
        if files is None:
            problems.append((task.id, "NO REFERENCE SOLUTION WRITTEN"))
            print(f"{task.id:<20} ??  no reference solution")
            continue
        passed, output = run(task, files)
        print(f"{task.id:<20} {'ok' if passed else 'FAILS'}")
        if not passed:
            problems.append((task.id, output[-700:]))

    print()
    if problems:
        print("=" * 70)
        for task_id, detail in problems:
            print(f"\n### {task_id}\n{detail}")
    else:
        print(f"all {len(tasks)} fixtures pass against a correct solution")

    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
