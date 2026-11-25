# Campus sign-in timing verification

Recorded: 2026-11-25
Observer: David Noyes
Tested revision: b49e84df723f14134b91fcb98d8450ed73410f76

## Acceptance criterion

David reports that Coty clarified the under-10-second requirement:
each application-controlled sign-in transition must complete in
under 10 seconds. Human time spent typing credentials, retrieving
or entering MFA codes, and enrolling MFA is excluded.

## Method

David manually timed each transition in the browser using a stopwatch.
The stopwatch was reset to zero before every measurement.

Timing started when the relevant button was clicked after any required
input was ready. Timing stopped when the destination page appeared.
Measurements include the redirects and page loading visible to the user.

These are approximate manual observations, not instrumented benchmarks.
One observation was recorded for each scenario.

## Results

| Transition | Approximate duration | Under 10 seconds |
| --- | ---: | --- |
| Campus sign-in button to credential form | 1.3 seconds | Yes |
| Submitted campus credentials to staff MFA page | 1.3 seconds | Yes |
| Submitted valid MFA code to staff welcome page | 1.3 seconds | Yes |
| Remembered campus sign-in to staff MFA page | 1.3 seconds | Yes |
| Submitted student credentials to staff refusal | 1.3 seconds | Yes |

All five measured transitions met the clarified acceptance criterion.

Remembered campus authentication skipped the campus password prompt.
It did not bypass staff MFA for a fresh staff login.

## Scope and limitations

- Results apply to the observed local demonstration at the tested revision.
- Human entry time is excluded according to the clarified requirement.
- These measurements do not establish an under-10-second total journey
  when manual credential entry, MFA interaction, or enrollment is included.
- Results do not establish performance under concurrent load or on
  other computers or deployments.
- Test-suite runtime is separate from these login measurements.

## Card status

The timing acceptance item is supported by these observations.
The overall Campus Credentials card remains In progress pending its
remaining review, documentation, and scope-clarification items.