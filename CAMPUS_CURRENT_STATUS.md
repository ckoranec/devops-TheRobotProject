# Campus sign-in: current verification status

Updated: 2026-11-25 | Owner: David Noyes
Implemented staff-SSO scope: verified. Overall card: In progress / awaiting acceptance.

## Completed evidence

- Reviewed application baseline: 69b830ccb2b5b99af667e621da41cf8c55c5b617.
- Latest supplied Windows suite: 121 passed in 66.66 seconds; no expected failures.
- Receiver-capacity refusal and expiry recovery: passed, committed as b49e84d.
- Explicit campus outcome logging: source-reviewed and exercised by outcome-focused
  tests, including request guards, credentials, token refusals, mapping/database
  failures, session expiry/revocation, provider logout and request capacity.
- This is not 100% branch coverage or an audit of every infrastructure exception.
- Shared mapping and begin_staff_login are imported from Colin; Shek owns shared MFA.
- Campus blueprint registered in shared app; launcher supplies matching signing keys.
- Remembered provider login, short-lived proof and provider logout are implemented.
- Live changed/expired token refusals and logs are documented in CAMPUS_VERIFY_RUN.md.
- Fresh-clone staff/student setup was demonstrated at de06780 (historical revision).
- Five independent application transitions took approximately 1.3, 2.6, 3.9, 5.2,
  and 6.5 seconds at b49e84d. Coty's reported criterion excludes human entry time.
- Browser smoke test completed November 25 at repository HEAD 69b830c. Supplied
  Git status showed documentation changes only; no tracked application edits.
- Staff denied before MFA, admitted after MFA, denied after logout; remembered
  provider login still requested MFA; provider logout restored the form;
  campus_student authenticated at provider but was refused staff access.
- Logs: staff MFA success at 15:50:20; provider reuse at 15:51:22; provider logout
  at 15:52:48; student password acceptance and no_staff_role at 15:53:33.
- Earlier Caps Lock credential errors and MFA expirations were resolved before
  successful completion. No password or authenticator reset was performed.

## Documentation deliverables prepared

README_CAMPUS_SSO.md is a compact quick start with a one-page PDF rendering.
CAMPUS_SETUP_DETAILS.md preserves the detailed initializer, separate-terminal
instructions, all five variable names, account guidance and troubleshooting.
The printable Campus SSO demonstration guide explains code, ownership and evidence.
These prepared documents must be saved/reviewed and committed through David's clone;
their generation does not claim they have already been pushed.

## Remaining decisions, not unperformed smoke tests

1. Shared MFA duration: the supplied local source and reviewed baseline still show
   PENDING_SECONDS =30. Shek reports 300; verify the published change after pulling.
   Expiry enforcement already passes, but that does not establish five minutes.
2. Customer-order scope: detailed milestones use the staff destination; customer
   ordering/tracking integration was not demonstrated. Obtain Coty's acceptance
   of the staff scope or the customer destination and owner interface.

No pending item remains to rerun the November 25 smoke test or create this guide.
A later application change may justify a new regression/smoke run.

## Supporting records

CAMPUS_SMOKE_TEST_2026-11-25.md; CAMPUS_VERIFY_RUN.md;
CAMPUS_TIMING_VERIFICATION.md; campus test files in backend/auth and campus_sso.
Passwords, tokens, signing keys and MFA codes are excluded from these documents.