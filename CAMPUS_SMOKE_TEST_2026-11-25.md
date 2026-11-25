# Campus staff-SSO smoke test

Date: 2026-11-25
Observer: David Noyes
Environment: Windows, regular Microsoft Edge, local campus demo
Repository HEAD: 69b830ccb2b5b99af667e621da41cf8c55c5b617

The Git status supplied after the test showed only
CAMPUS_CURRENT_STATUS.md modified. No tracked application-source
changes were reported.

## Result

The implemented staff-SSO browser flow passed the checks below.
Results combine David's browser observations, screenshots, and
application log excerpts.

| Check | Result |
| --- | --- |
| Campus staff credentials reached MFA | Passed |
| Staff access before completed MFA was denied | Passed |
| Valid MFA led to the staff welcome page | Passed |
| Staff logout removed access to /staff | Passed |
| Remembered campus login skipped the password form but requested MFA | Passed |
| Provider logout restored the campus credential form | Passed |
| Campus student credentials led to staff refusal | Passed |
| Student could not access /staff | Passed |

## Selected log evidence

Application log:

    2026-11-25 15:50:03 | INFO | event=campus_sso | result=identity_accepted | campus_id=CAMPUS-1001
    2026-11-25 15:50:20 | INFO | 2FA verification success | user_id=1 (staff_test)
    2026-11-25 15:53:33 | INFO | event=campus_sso | result=no_staff_role | campus_id=CAMPUS-2001

Provider log:

    2026-11-25 15:51:22,514 | INFO | event=campus_provider | result=session_reused | campus_id=CAMPUS-1001
    2026-11-25 15:52:48,783 | INFO | event=campus_provider | result=logout | campus_id=-
    2026-11-25 15:53:33,683 | INFO | event=campus_provider | result=password_accepted | campus_id=CAMPUS-2001

Spacing was normalized from the supplied terminal output.
No passwords, tokens, cookies, signing keys, or MFA codes are included.

## Interpretation

Campus identity acceptance starts the shared pending-login flow.
It does not grant staff access or claim that MFA is complete.

The student authenticated successfully at the campus provider but
was refused staff authorization because there was no staff mapping.

Remembered provider authentication and staff authentication are
separate. Provider-session reuse did not bypass fresh staff MFA.

## Issues encountered and resolved during the run

Initial campus credential failures were traced by David to Caps Lock.
A read-only check confirmed the campus_staff account and password
matched the main project's database. No password reset was performed.

Earlier MFA attempts expired. The application recorded:
- 15:47:13: Pending MFA expired.
- 15:48:09: Pending MFA expired.

A later fresh attempt completed MFA successfully at 15:50:20.
The expired attempts are not counted as successful sign-ins.

## Remaining dependencies

The supplied local source still shows PENDING_SECONDS =30.
The requested 300-second setting requires shared-owner publication
and verification. No shared MFA code was changed for this smoke test.

Customer ordering/tracking access was not tested. Coty must clarify
whether that integration is required beyond the staff-site milestones.

## Related evidence

- Latest supplied automated campus suite: 121 passed in 66.66 seconds.
  This was a separate earlier run, not rerun as part of this browser test.
- CAMPUS_TIMING_VERIFICATION.md records the separately measured
  application transitions under Coty's clarified timing criterion.
- CAMPUS_VERIFY_RUN.md preserves earlier token-refusal and fresh-clone
  demonstrations.

Implemented staff-SSO scope: smoke-tested successfully.
Overall card: In progress, awaiting the remaining acceptance decisions.