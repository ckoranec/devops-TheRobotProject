# Easy Login with Campus Credentials — implementation and evidence, 2026-11-19

Keep the card In progress. This update does not establish under-10-second human login,
real university SSO, customer order access, or completion of shared-owner dependencies.
The card's customer description and its staff-only milestones differ: students must be
refused robot controls, but this does not imply they should be refused customer ordering.
Confirm that scope with Coty before marking the customer acceptance criterion complete.

## What changed

The separate provider now remembers campus authentication in a bounded, server-side,
in-memory session store. A browser session cookie holds only an opaque random ID. Records
contain the campus ID, a credential-change fingerprint, creation time and last-use time.
No passwords, tokens or MFA success flags are stored in that cookie.

A valid session on a new /login request produces a new signed token with the current state,
a unique jti and a 60-second lifetime. The staff receiver still checks the proof and calls
Colin's mapping and begin_staff_login functions. Fresh staff authentication still needs MFA.

Idle expiry is 15 minutes; absolute lifetime is one hour. These are explicit demo defaults,
not an assertion of a team-approved production policy. Provider logout, server restart,
server-side revocation, account deletion and password changes invalidate remembered access.
Clearing cookies removes browser access to the session; browser closure is not a reliable
server-side revocation mechanism because browsers can restore session cookies.

The store is thread-protected but serves one process only. Multiple workers need a shared
session backend. This local HTTP-only demo uses HttpOnly/SameSite=Lax cookies with Secure off;
a deployed HTTPS provider must use Secure cookies. Keep this as a local simulation.

## Checklist evidence

| Card item | Evidence / remaining work |
| --- | --- |
| Separate provider, fake-account login, signed expiring token | Provider tests and local launch on 5052 |
| Receiver token signature, expiry, request binding and replay refusal | Existing callback tests plus remembered-token replay test |
| Shared session handoff | Actual import of Colin's begin_staff_login; identity and equivalent-state tests |
| Staff mapping and no-role refusal | Real database lookup; campus_student can authenticate at provider but receives no_staff_role at receiver |
| Successful end-to-end sign-in | Existing integrated real MFA test plus new remembered-provider/staff-logout test |
| Success and refusal logs | test_campus_card_evidence.py prints real captured callback lines with isolated test data |
| Provider credential/refusal outcomes | Provider logger records password_accepted, invalid_credentials, invalid_request, form_refused, request_expired, session reuse/expiry/revocation, capacity and logout outcomes |
| No additional campus registration | Provider reads existing accounts; no registration screen. Admin seed/mapping is test setup, not user registration |
| Remembered university login | New provider session suite: fresh proof, cookie properties, idle/absolute expiry, invalid cookie, restart, credential change, logout, staff MFA boundary |
| Under 10 seconds | NOT VERIFIED. Prior manual fresh-login results exceeded 10 seconds |
| Exact shared app.py launch | Registered by Shek in commit 7933e98; shared-factory tests exercise it directly. Windows launch/fresh-clone verification remains |
| Shared pending-MFA timeout | Two strict XFAILs remain. Colin's handoff lacks timestamp creation and shared MFA lacks expiry enforcement |

Identity acceptance logs mean handed to MFA, not that MFA succeeded. Shared MFA logs its own
success. Provider logout does not terminate an existing staff session; staff logout does not
terminate provider login. To end both, use both logout actions. This is not global single logout.

## Reproduce printable log evidence

Run from your clone (all accounts/databases/keys used here are disposable):

```powershell
.\.venv\Scripts\python.exe -m pytest backend/auth/test_campus_card_evidence.py -q -s
```

The four checked cases are accepted identity, student without staff mapping, exactly one
changed token character, and a correctly signed expired token. The printed lines come from
asserted application log messages, not invented screenshots. These tests never modify live users.
For normal local demo output, receiver logs are backend/auth/account_activity.log; provider
logs are campus_sso/provider_activity.log when launched as a module. Do not commit either log.

## Browser demonstration

1. Pull the latest human-only and run tests. Start `python -m campus_sso.run_demo` from the clone.
2. At http://127.0.0.1:5052/logout sign out of provider, then start at http://127.0.0.1:5051/campus.
3. Sign in as campus_staff using your existing fake credentials. Complete genuine staff MFA.
4. Return to /campus and use **Log out of campus session** (staff logout). Leave provider login active.
5. Start campus sign-in again. The provider returns with new proof without another password prompt.
6. Verify the staff site still requests MFA. A previously used MFA timestep code may be refused;
   wait for a new authenticator code rather than weakening one-use validation.
7. Use **Sign out of campus provider**, confirm logout, then start fresh campus sign-in. Credentials
   must be requested again. Sign out of staff separately if a staff session is still active.
8. Sign in as campus_student. Its correct campus password is accepted; staff mapping is refused.

## Timing worksheet

Record three runs for each scenario. Start when clicking campus sign-in; stop when the intended
protected welcome page is visible. Keep failures/retries in the record, including MFA retries.

| Scenario | Run 1 | Run 2 | Run 3 | Includes human entry/MFA? |
| --- | --- | --- | --- | --- |
| Fresh provider login + existing staff MFA enrollment | pending | pending | pending | Yes |
| Remembered provider login + fresh staff MFA | pending | pending | pending | Yes, MFA |
| Returning already-verified staff session | pending | pending | pending | No fresh login |

Separately record credential submit -> MFA page and Verify -> welcome to isolate server delays.
Do not replace full-flow measurements with those segments. If required manual MFA keeps full
login above 10 seconds, bring the measured scope to Coty; the target is not automatically waived.

## Coty's cleanup questions

1. Runtime resolve_staff already calls database.get_staff_id_by_campus_id and checks that the
   resulting staff account exists. Runtime MFA handoff imports Colin's actual begin_staff_login.
   The old campus_sso_demo.py remains a labelled historical stand-in, not used by run_demo or
   campus_staff_app. Stand-ins in isolated callback unit tests remain useful; integrated tests
   also exercise the real shared implementation. No shared file needs deletion.
2. campus_directory.py has no build_directory or authenticate definitions in the checked commit.
   Its production functions use campus_accounts. No old in-memory implementation remains there.
3. The source tree has only backend/auth/campus_login.py. The separate provider is already named
   campus_sso/campus_provider.py and tests are campus_sso/test_campus_provider.py. The remaining
   campus_login.py provides token_serializer used by the provider, so deleting it breaks imports.
4. Five actual comment reviews (no need to claim every comment helps):

| Comment in campus_directory.py | Harder without it? | Reason |
| --- | --- | --- |
| Require an existing database so a mistaken path cannot create another one. | Yes | Explains why SQLite mode=rw matters |
| Create only the campus table; preserve existing tables and records. | Slightly | Explains the ownership boundary beyond SQL syntax |
| Reject incomplete setup before making database changes. | Usually no | The adjacent input check and exception already express this |
| Repeated setup adds missing identities without resetting existing ones. | Yes | Explains deliberate idempotence and password preservation |
| Return identity information without credentials or staff-site permissions. | Yes | Explains the distinction between identity and authorization |

These are discussion answers grounded in current code. No teammate code was edited to simplify comments.
