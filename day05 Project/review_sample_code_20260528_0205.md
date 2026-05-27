# Code Review Report

**File:** `sample_code.py`
**Date:** 2026-05-28 02:05
**Overall Risk Level:** 🔴 CRITICAL

---

## Executive Summary

`sample_code.py` contains multiple critical vulnerabilities and runtime bugs that make it unsafe for any production environment. Hardcoded credentials, a direct SQL injection vector, and an unguarded path traversal vulnerability represent immediate security threats requiring remediation before any deployment. Code quality is poor throughout — all functions lack type hints, docstrings, and meaningful naming — significantly increasing the risk of future defects being introduced.

---

## 🐛 Bugs

| ID | Line | Severity | Description |
|----|------|----------|-------------|
| BUG_001 | 10 | 🔴 CRITICAL | `user_id` is never checked for `None` before being concatenated into the SQL string on line 19. Passing `None` raises a `TypeError` at runtime. |
| BUG_002 | 19 | 🔴 CRITICAL | SQL string concatenation assumes `user_id` is already a `str`. Passing an integer (a common case for IDs) raises `TypeError: can only concatenate str (not "int") to str`. |
| BUG_003 | 28 | 🟠 HIGH | Division by `z` on line 30 has no zero-check. If `flag1` is `True` and `z == 0`, an unhandled `ZeroDivisionError` crashes the function. |
| BUG_004 | 36 | 🔴 CRITICAL | `get_user(username)` may return `None` if no user is found. On line 37, `stored[3]` then raises `TypeError: 'NoneType' object is not subscriptable`, crashing `authenticate` entirely. |
| BUG_005 | 37 | 🟠 HIGH | `stored[3]` uses a hardcoded magic index with no bounds check. If the row returned has fewer than 4 columns, this raises an `IndexError` at runtime. |
| BUG_006 | 36 | 🟡 MEDIUM | `authenticate` has no explicit `return False` on the failure path. If `stored[3] != hashed`, the function falls through and implicitly returns `None`, breaking strict equality callers using `== False` or `is False`. |
| BUG_007 | 14–17 | 🟡 MEDIUM | The database `conn` and `cursor` in `get_user` are never closed. There is no `finally` block or context manager, causing a connection leak on any exception. |
| BUG_008 | 43 | 🟡 MEDIUM | `open("/reports/" + filename, "w")` has no exception handling. A missing directory or permission error raises an unhandled `FileNotFoundError` or `PermissionError` with no diagnostic context. |

### Bug Severity Breakdown

```
CRITICAL  ███████████░░░░░░░░░  3 findings
HIGH      ███████░░░░░░░░░░░░░  2 findings
MEDIUM    ████████████░░░░░░░░  3 findings
```

---

## ⚠️ Code Quality

| ID | Line | Severity | Description |
|----|------|----------|-------------|
| QUALITY_001 | 9 | 🟠 HIGH | Missing type hints on `get_user` — parameter `user_id` and return type are unspecified. |
| QUALITY_002 | 9 | 🟠 HIGH | Missing docstring on `get_user` — no description of purpose, parameters, or return value. |
| QUALITY_003 | 9 | 🟡 MEDIUM | `get_user` violates single responsibility — handles both DB connection logic and data retrieval; connection setup should be extracted. |
| QUALITY_004 | 23 | 🟠 HIGH | Poor parameter naming — `x`, `y`, `z`, `flag1`, `flag2`, `flag3` are meaningless. Use descriptive names such as `multiplier`, `offset`, `divisor`, `should_divide`. |
| QUALITY_005 | 23 | 🟠 HIGH | Missing type hints on `process_data` — all 7 parameters and the return type are unspecified. |
| QUALITY_006 | 23 | 🟠 HIGH | Missing docstring on `process_data` — especially critical given the cryptic parameter names. |
| QUALITY_007 | 23 | 🟠 HIGH | `process_data` violates single responsibility — performs transformation, division, hashing, and filtering in a single function. |
| QUALITY_008 | 26 | 🟡 MEDIUM | Non-pythonic iteration — `for i in range(len(data))` should be `for item in data`, or `enumerate(data)` if an index is required. |
| QUALITY_009 | 27 | 🟡 MEDIUM | Non-pythonic `None` comparison — `data[i] != None` should be `data[i] is not None`. |
| QUALITY_010 | 28 | 🔵 LOW | Poor variable naming — `temp` is vague; use a name reflecting what the value represents (e.g., `transformed_value`). |
| QUALITY_011 | 26 | 🟡 MEDIUM | Entire loop body is a candidate for a list comprehension or extracted helper functions, reducing the readability burden on the caller. |
| QUALITY_012 | 37 | 🟠 HIGH | Missing type hints on `authenticate` — parameters and return type (`Optional[bool]`) are unspecified. |
| QUALITY_013 | 37 | 🟠 HIGH | Missing docstring on `authenticate`. |
| QUALITY_014 | 40 | 🟠 HIGH | Magic index `stored[3]` — using a raw positional index on a DB row is fragile and unreadable; use named fields, a `namedtuple`, or a dataclass. |
| QUALITY_015 | 37 | 🟡 MEDIUM | `authenticate` violates single responsibility — handles password hashing, credential comparison, and user lookup in one function. |
| QUALITY_016 | 37 | 🟡 MEDIUM | Inconsistent return behaviour — returns `True` on success but implicitly returns `None` on failure; should explicitly return `False`. |
| QUALITY_017 | 44 | 🟠 HIGH | Missing type hints on `save_report` — parameters and return type are unspecified. |
| QUALITY_018 | 44 | 🟠 HIGH | Missing docstring on `save_report`. |
| QUALITY_019 | 44 | 🟡 MEDIUM | String concatenation for path building — use `os.path.join("/reports/", filename)` for cross-platform correctness and readability. |
| QUALITY_020 | 1 | 🔵 LOW | No module-level docstring — the file has no description of its overall purpose or contents. |
| QUALITY_021 | 23 | 🔵 LOW | Excessive parameters (7) in `process_data` — consider grouping related flags into a config dataclass or splitting into focused functions. |

### Key Quality Themes

> **Naming** — `x`, `y`, `z`, `flag1`–`flag3`, `temp`, and `stored` are all insufficiently descriptive and increase cognitive load for every future reader.

> **Type Hints & Docstrings** — Completely absent across all four functions. This is the baseline for maintainable, reviewable Python code.

> **Single Responsibility** — Every function does too much. Decomposing them will naturally reduce bug surface area and improve testability.

> **Pythonic Patterns** — Raw index iteration and `!= None` comparisons should be eliminated in favour of idiomatic Python.

---

## 🔒 Security

| ID | Line | Severity | Description |
|----|------|----------|-------------|
| SEC_001 | 5 | 🔴 CRITICAL | **Hardcoded API key** — `"sk-prod-1234567890abcdef"` is exposed directly in source. Any version control history or repository access permanently leaks this credential. Load from environment variables or a secrets manager. |
| SEC_002 | 6 | 🔴 CRITICAL | **Hardcoded database password** — `"admin123"` is stored in plaintext source. Use `os.environ` or a secrets manager (e.g., AWS Secrets Manager, HashiCorp Vault). |
| SEC_003 | 19 | 🔴 CRITICAL | **SQL Injection** — `user_id` is concatenated directly into the query string with no sanitisation. An attacker can manipulate the query to dump, modify, or delete arbitrary data. **Fix:** Use parameterised queries: `cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))` |
| SEC_004 | 34 | 🟠 HIGH | **Broken password hashing (MD5)** — MD5 is cryptographically broken, unsalted, and trivially reversible via rainbow tables. Replace with `bcrypt`, `scrypt`, or `argon2-cffi`. |
| SEC_005 | 42 | 🟠 HIGH | **Path traversal vulnerability** — `filename` is concatenated into the file path without sanitisation. An attacker supplying `../../etc/passwd` can write files outside `/reports/`. **Fix:** Sanitise with `os.path.basename(filename)` and assert the resolved path starts with the intended base directory. |
| SEC_006 | 9 | 🟡 MEDIUM | **Overprivileged database connection** — the application connects as a root-equivalent user. Apply the principle of least privilege: create a dedicated DB user with only the permissions the application actually requires. |
| SEC_007 | 36 | 🟡 MEDIUM | **Insecure direct object reference** — `get_user(username)` result is indexed at `[3]` with no verification that the returned record belongs to the authenticating user, potentially enabling account enumeration or authentication bypass via manipulated input. |
| SEC_008 | 30 | 🔵 LOW | **MD5 for data fingerprinting** — while less severe than password hashing with MD5, using it for any integrity or fingerprinting purpose is inadvisable given known collision vulnerabilities. Use SHA-256 at minimum. |

### Security Severity Breakdown

```
CRITICAL  ███████████████░░░░░  3 findings
HIGH      ██████████░░░░░░░░░░  2 findings
MEDIUM    ██████░░░░░░░░░░░░░░  2 findings
LOW       ███░░░░░░░░░░░░░░░░░  1 finding
```

---

## ✅ Top 3 Priority Fixes

### 1. 🔒 Eliminate Hardcoded Credentials and SQL Injection (SEC_001, SEC_002, SEC_003)

These three issues together represent a complete compromise path: credentials leaked from source enable database access, and the SQL injection vector allows an unauthenticated attacker to exfiltrate or destroy data directly. Address all three before any other work.

```python
# Before
API_KEY = "sk-prod-1234567890abcdef"
DB_PASSWORD = "admin123"
query = "SELECT * FROM users WHERE id = " + user_id

# After
import os
API_KEY = os.environ["API_KEY"]
DB_PASSWORD = os.environ["DB_PASSWORD"]
cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
```

---

### 2. 🔒 Replace MD5 Password Hashing and Fix `authenticate` (SEC_004, BUG_004, BUG_005, BUG_006)

MD5 password hashing is trivially broken, and the `authenticate` function will crash on a `None` return from `get_user` before the hash comparison is even reached. Both must be fixed together.

```python
# Before
import hashlib
hashed = hashlib.md5(password.encode()).hexdigest()
stored = get_user(username)
if stored[3] == hashed:
    return True

# After
import bcrypt
from typing import Optional

def authenticate(username: str, password: str) -> bool:
    stored = get_user(username)
    if stored is None or len(stored) < 4:
        return False
    stored_hash: bytes = stored[3]
    return bcrypt.checkpw(password.encode(), stored_hash)
```

---

### 3. 🔒 Sanitise the File Path to Prevent Path Traversal (SEC_005, BUG_008)

The unsanitised `filename` parameter allows directory traversal attacks. This fix also adds the missing exception handling called out in BUG_008.

```python
# Before
file = open("/reports/" + filename, "w")

# After
import os

BASE_DIR = "/reports/"

def save_report(filename: str, content: str) -> None:
    safe_name = os.path.basename(filename)
    full_path = os.path.realpath(os.path.join(BASE_DIR, safe_name))
    if not full_path.startswith(os.path.realpath(BASE_DIR)):
        raise ValueError(f"Invalid filename rejected: {filename!r}")
    try:
        with open(full_path, "w") as file:
            file.write(content)
    except (FileNotFoundError, PermissionError) as exc:
        raise RuntimeError(f"Failed to save report to {full_path!r}") from exc
```

---

## Overall Scores

| Category | Score | Rating |
|----------|-------|--------|
| 🐛 **Bugs** | 2 / 10 | 🔴 Critical — 3 crash-level defects in core paths |
| ⚠️ **Code Quality** | 2 / 10 | 🔴 Poor — naming, type hints, and docstrings absent throughout |
| 🔒 **Security** | 1 / 10 | 🔴 Critical — hardcoded secrets, SQLi, and path traversal present simultaneously |
| 📋 **Overall** | **2 / 10** | 🔴 **Not production-ready** |

> **Verdict:** This file must not be deployed in its current state. The combination of hardcoded credentials, SQL injection, path traversal, and broken authentication constitutes an unacceptable risk profile. Resolve all `CRITICAL` findings before any further review cycle.