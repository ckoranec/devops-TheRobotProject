# Campus integration verification

Recorded: 2026-11-19T12:52:04.1297269-05:00
Tested commit: 2f8c3191e9a7cf919003079f8ce4e111531a444e

## Windows automated tests
............................x...........x............................... [ 84%]
.............                                                            [100%]
=========================== short test summary info ===========================
XFAIL backend/auth/test_campus_scope.py::test_shared_mfa_refuses_valid_code_after_pending_expiry - Shared MFA accepts a valid code after pending expiry; requires owner fix
XFAIL backend/auth/test_campus_staff_app.py::test_pending_campus_mfa_expires - Shared MFA routes do not enforce pending expiry yet; owner dependency
83 passed, 2 xfailed in 66.35s (0:01:06)

## Isolated callback and logging evidence
These tests use temporary accounts, databases and keys.
They do not demonstrate attacks against the running browser services.
============================= test session starts =============================
platform win32 -- Python 3.15.0, pytest-9.2.0, pluggy-1.7.0 -- C:\Users\noyes\PycharmProjects\devops-TheRobotProject\.venv\Scripts\python.exe
cachedir: .pytest_cache
rootdir: C:\Users\noyes\PycharmProjects\devops-TheRobotProject
plugins: Faker-40.44.0
collecting ... collected 4 items

backend/auth/test_campus_card_evidence.py::test_card_evidence[accepted-identity_accepted-302] ISOLATED INTEGRATION EVIDENCE: accepted -> HTTP 302
event=campus_sso | result=identity_accepted | campus_id=CAMPUS-1001
PASSED
backend/auth/test_campus_card_evidence.py::test_card_evidence[student-no_staff_role-403] ISOLATED INTEGRATION EVIDENCE: student -> HTTP 403
event=campus_sso | result=no_staff_role | campus_id=CAMPUS-2001
PASSED
backend/auth/test_campus_card_evidence.py::test_card_evidence[changed-invalid_signature-403] ISOLATED INTEGRATION EVIDENCE: changed -> HTTP 403
event=campus_sso | result=invalid_signature | campus_id=-
PASSED
backend/auth/test_campus_card_evidence.py::test_card_evidence[expired-expired_token-403] ISOLATED INTEGRATION EVIDENCE: expired -> HTTP 403
event=campus_sso | result=expired_token | campus_id=-
PASSED

============================== 4 passed in 5.78s ==============================

## Browser observations reported by David
- Campus staff completes MFA and reaches the staff welcome page.
- Campus student is refused staff access.
- Remembered campus login skips the repeated campus password prompt.

## Outstanding
- Live changed-token and expired-token demonstrations.
- Final logging coverage review.
- Provider logout browser confirmation.
- Under-10-second measurements by login scenario.
- Fresh-clone verification.
- Shared pending-MFA expiry remains a known gap.
- Customer-order versus staff-only scope clarification.

## Live token-refusal verification - 2026-11-20

Live HTTP demonstration against the running local provider and staff application.

- Changed exactly one character of a genuine provider token.
- Callback returned HTTP 403; protected staff page returned HTTP 403.
- Obtained a fresh token and left it unchanged for 65 seconds.
- Expired-token callback returned HTTP 403; staff page returned HTTP 403.
- Provider remembered the campus login between the two requests.
- Verified the expected newly appended application log entries.

Observed logs:

    2026-11-20 09:35:35 | INFO | event=campus_sso | result=invalid_signature | campus_id=-
    2026-11-20 09:36:40 | INFO | event=campus_sso | result=expired_token | campus_id=-

Both live token-refusal demonstrations passed.
No passwords, token values, or signing keys are included.
The exact running revision was not captured by the demonstration script.
Provider logout, timing, fresh-clone setup, and MFA expiry are not established by this run.
