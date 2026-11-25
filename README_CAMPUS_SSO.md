# Campus SSO: one-page quick start
David Noyes | 2026-11-25 | Windows PowerShell

## First setup
Clone human-only into a new folder; stop if a command fails.

```powershell
git clone --branch human-only https://github.com/ckoranec/devops-TheRobotProject.git campus-demo
Set-Location campus-demo
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Initialize the NEW database once using section 2 of CAMPUS_SETUP_DETAILS.md.
It calls Colin's initializer and privately prompts for the two campus passwords.
Do not delete, reseed, or overwrite an existing users.db or authenticator database.

## Start and sign in
```powershell
.\.venv\Scripts\python.exe -m campus_sso.run_demo
```
Wait for READY; open http://127.0.0.1:5051/campus. Keep the terminal open.
Ctrl+C stops both services. Stop old servers before starting another launcher.

- campus_staff: use the password chosen for THIS clone; complete staff MFA.
- campus_student: valid campus credentials are refused staff access.
- New MFA enrollment: use a separately labelled authenticator entry for each clone.
- Remembered campus login skips the campus form, not fresh staff MFA.
- Provider logout: http://127.0.0.1:5052/logout; confirm to restore the form.
- Staff logout separately removes staff access. Use 127.0.0.1 consistently.

## Configuration
FLASK_SECRET_KEY: shared staff session. CAMPUS_SSO_SIGNING_KEY: provider signs,
receiver verifies; values must match. CAMPUS_IDP_COOKIE_SECRET: provider Flask
session cookie. Runtime keys are random strings of at least 32 characters.
run_demo generates missing keys once and passes the environment to both services.
CAMPUS_FAKE_STAFF_PASSWORD and CAMPUS_FAKE_STUDENT_PASSWORD are seeding inputs.
Passwords and key VALUES stay private, never in Git, logs, or this README.
See CAMPUS_SETUP_DETAILS.md for separate-terminal commands and troubleshooting.

## Verify
```powershell
$campusTests = @(Get-ChildItem backend/auth/test_campus_*.py; Get-ChildItem campus_sso/test_*.py) | Select-Object -ExpandProperty FullName
.\.venv\Scripts\python.exe -m pytest @campusTests -q -ra --tb=short
```
Logs: backend/auth/account_activity.log; campus_sso/provider_activity.log.
121 campus tests passed in the latest supplied run. See CAMPUS_CURRENT_STATUS.md,
CAMPUS_SMOKE_TEST_2026-11-25.md, and CAMPUS_TIMING_VERIFICATION.md for evidence.
Staff-SSO smoke test passed. Customer-order scope and the shared 300-second
MFA setting remain open. This fake-provider milestone is a local simulation.