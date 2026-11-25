# Campus SSO: detailed setup companion

David Noyes | Updated November 25, 2026

Campus sign-in runs through Shek’s shared application, Colin’s staff mapping
and `begin_staff_login`, then staff MFA. The fake campus provider remains a
separate service. Fresh-clone verification at `de06780` produced 83 passed,
2 expected failures, successful staff access, and student refusal.

## 1. Install in a fresh clone

Run in Windows PowerShell:

```powershell
git clone --branch human-only https://github.com/ckoranec/devops-TheRobotProject.git campus-demo
Set-Location campus-demo
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Stop if any command fails. Use the explicit `.venv` Python commands below.

## 2. Initialize the fresh database once

Choose two fake campus passwords at the hidden prompts. Remember them privately.
This calls Colin’s initializer and suppresses its printed demonstration credentials.

```powershell
.\.venv\Scripts\python.exe -c "import os,getpass,contextlib,io; from pathlib import Path; from backend.auth.database import DB_FILE; assert not Path(DB_FILE).exists(), 'Database already exists; do not rerun initialization'; os.environ['CAMPUS_FAKE_STAFF_PASSWORD']=getpass.getpass('Choose campus_staff password: '); os.environ['CAMPUS_FAKE_STUDENT_PASSWORD']=getpass.getpass('Choose campus_student password: '); from backend.auth.initialize_database import initialize_database; output=io.StringIO(); ctx=contextlib.redirect_stdout(output); ctx.__enter__(); initialize_database(); ctx.__exit__(None,None,None); print('Database initialized.')"
```

The initializer creates staff/campus tables, seeds demonstration accounts, and
maps `CAMPUS-1001` to `staff_test`. `CAMPUS-2001` has no staff mapping.
Do not rerun against an existing database: the current mapping insert can
raise a duplicate-key error. Do not delete an existing working MFA database.

## 3. Start both services

Stop older servers with Ctrl+C, then run:

```powershell
.\.venv\Scripts\python.exe -m campus_sso.run_demo
```

Wait for READY and open http://127.0.0.1:5051/campus.
Keep the terminal open; Ctrl+C stops both services.

- `campus_staff`: use the chosen campus password, enroll in MFA if new,
  and complete MFA to reach the staff welcome page.
- `campus_student`: campus credentials succeed, but staff access is refused.
- Provider logout: http://127.0.0.1:5052/logout — confirm logout.
  The next campus sign-in must request credentials again.
- Staff logout and provider logout are separate. Remembered provider login
  skips the campus password prompt; a fresh staff login still requires MFA.

Use `127.0.0.1` consistently. For a separate test clone, use an InPrivate
window and a separately labelled authenticator entry.

## Configuration and shared connection

| Environment variable | Purpose |
| --- | --- |
| FLASK_SECRET_KEY | Shared staff application session signing |
| CAMPUS_SSO_SIGNING_KEY | Same token-signing value in provider and receiver |
| CAMPUS_IDP_COOKIE_SECRET | Separate provider cookie-signing secret |
| CAMPUS_FAKE_STAFF_PASSWORD | Campus staff password during database seeding |
| CAMPUS_FAKE_STUDENT_PASSWORD | Campus student password during database seeding |

Runtime keys must be random and at least 32 characters. `run_demo` generates
missing keys once, preserves configured keys, and passes matching values to
both services. Never commit keys or send their values in team chat.

Shek’s factory registers `register_campus_sso(app)`. Campus registration accepts
`CAMPUS_SSO_SIGNING_KEY` from `app.config`, falling back to the environment only
when absent. It does not replace the shared staff session key.

For separate terminals, configure the same signing key in both environments:
run `python -m campus_sso.campus_provider` for port 5052 and
`python -m backend.auth.app` for port 5051, using the virtual environment.
The shared-app command alone does not start the provider.

## Verify

```powershell
$campusTests = @(
    Get-ChildItem '.\backend\auth\test_campus_*.py' -File
    Get-ChildItem '.\campus_sso\test_*.py' -File
) | Select-Object -ExpandProperty FullName
.\.venv\Scripts\python.exe -m pytest @campusTests -q -rx --tb=short
```

Staff events: `backend/auth/account_activity.log`.
Provider events: `campus_sso/provider_activity.log`.
See `CAMPUS_VERIFY_RUN.md` for live token-refusal, logout, and fresh-clone evidence.

Current status: 121 tests passed in the latest supplied Windows run. Pending-MFA
expiry enforcement passes; the observed setting remains 30 seconds at 69b830c.
The requested 300-second value awaits publication/verification. Browser smoke
testing passed on November 25. Measured transitions were 1.3-6.5 seconds, excluding
human entry time per Coty's clarification. Customer-order destination remains
an acceptance question. See CAMPUS_CURRENT_STATUS.md for the scoped conclusion.

## Credential handling and troubleshooting

Existing clone: use its original campus passwords. Changing the seeding environment
variables or rerunning seeding does not reset existing campus passwords. Fresh clone:
choose new private demonstration passwords. Password hashes cannot reveal the old
password. Staff credentials and campus credentials are separate accounts.

The three runtime key values are distinct from account passwords. For a two-terminal
start, securely configure the same CAMPUS_SSO_SIGNING_KEY in both processes; do not
generate it independently in each. Give the staff process FLASK_SECRET_KEY and the
provider CAMPUS_IDP_COOKIE_SECRET. At reviewed revision 69b830c, the shared factory
also resolves a provider-cookie variable, though it does not use that value for the
staff cookie. The launcher avoids inconsistent independent key generation.

The provider's remembered-login cookie contains an opaque identifier linked to
server memory. Restarting the provider clears those remembered sessions. The Flask
provider cookie holds signed form/session state; it is not the same cookie.

If login fails: check Caps Lock and the clone's password. If MFA fails: use the
correct authenticator entry, wait for any cooldown, and start a fresh sign-in.
Do not delete a working MFA database to fix a timing or wrong-code problem.
Never print environment values, submit passwords in team chat, or commit logs
containing tokens. Existing private values are not replaced by these documents.