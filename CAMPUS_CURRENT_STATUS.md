# Campus sign-in: current verification status

Updated: 2026-11-25
Owner: David Noyes
Card: Easy Login with Campus Credentials
Status: In progress

## Latest verified contribution

Revision: 92e3718870181be70a892bfe3b320a5a974f332a

David's supplied Windows results:
- New outcome-logging tests: 16 passed in 12.69 seconds.
- Complete campus integration suite: 120 passed in 68.65 seconds.
- No failed or expected-failure tests were reported.
- Commit and push succeeded; the subsequent Git check reported a clean
  working folder and zero local-only or remote-only commits.

The tests ran before committing the tested changes. The pull before
pushing reported "Already up to date."

Test-suite duration is not a measurement of login speed.

## Working integration

- Campus sign-in uses Colin's campus-to-staff mapping.
- Campus sign-in imports Colin's shared begin_staff_login function.
- Shek's shared application registers the campus blueprint.
- A fresh staff login still requires staff MFA.
- Remembered campus authentication skips repeated campus password entry.
- Campus provider logout ends remembered campus authentication.
- Provider logout and staff logout are separate operations.
- The launcher starts both services with matching token-signing keys.

## Logging verification

Existing automated tests and live evidence cover:
- Accepted campus identity and refusal of an identity without staff mapping.
- Changed-token and expired-token refusals.
- Remembered campus login.

The new guard tests cover:
- Unexpected hostname and nonlocal address refusals.
- Oversized requests.
- Pending-MFA expiry encountered on campus routes.
- An unavailable staff mapping database.

The new outcome tests cover:
- Expired provider forms and missing request state.
- Invalid form protection values.
- Empty usernames and passwords.
- An unavailable campus directory.
- Provider session capacity.
- An account disappearing during authentication.
- Missing tokens, wrong audience, and wrong request state.
- A callback without its original pending request.
- Expired, unknown, and revoked remembered sessions.
- Refused and successful provider logout.

The tests check relevant log messages and refusal behavior using
temporary accounts and databases. They include checks that submitted
passwords, tokens, cookies, or form values are not present in captured
logs, as applicable to each test.

This is an outcome-focused review, not a claim of 100% code coverage.
Receiver request-capacity logging is present in the reviewed source;
a targeted runtime assertion for that path remains to be recorded
before calling the logging test inventory complete.

## Shared MFA status

Pending-MFA expiry enforcement now passes the integration tests.
Earlier expected failures in CAMPUS_VERIFY_RUN.md are historical.

The latest supplied local setting was PENDING_SECONDS = 30.
Requested 300 seconds. Confirm the owner-controlled duration
change separately; successful expiry tests alone do not prove that
the configured duration is five minutes.

## Previously demonstrated

See CAMPUS_VERIFY_RUN.md for dated evidence:
- Staff completes MFA and reaches the staff welcome page.
- A campus student without staff mapping is refused.
- Live changed-token and expired-token requests are refused and logged.
- Provider logout restores the campus credential prompt.
- Fresh-clone setup, new MFA enrollment, and staff/student outcomes
  were verified at revision de06780.

The earlier fresh-clone demonstration does not establish that every
later revision has also been tested from a fresh clone.

## Remaining work

- Complete the final logging test inventory and document its scope.
- Record login timings against the under-10-second requirement.
- Label fresh login, remembered-provider login plus MFA, and existing
  verified staff access as different timing scenarios.
- Confirm the current revision's browser flow after the recent changes.
- Confirm the requested five-minute MFA duration with its shared owner.
- Clarify customer ordering/tracking versus the demonstrated staff page.
- Confirm the setup README meets one-page requirement.

Keep Card 4 In progress.