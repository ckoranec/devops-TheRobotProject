# Campus SSO setup and integration — David Noyes, 2026-11-18

## Status and ownership

This is an intermediate campus-scope correction, not a completed authentication release.
Campus routes are one `campus` blueprint; helpers, tests and launchers do not need blueprints.
The provider stays a separate service on 5052. The receiving shared app runs on 5051.
No teammate source files or real database tables are changed by this update.

Integration checked against human-only commit 69aaa1f7acff110a8bcf30e86f2a6fe07a6d4ced:
- Campus now directly imports Colin's staff_login.begin_staff_login(staff_id).
- The duplicate campus session-start function has been removed; there is no fallback copy.
- Colin's initializer now calls create_staff_campus_mapping().
- Mapping lookup still imports and uses Colin's database functions.
- The initializer creates the mapping table, but does not itself seed CAMPUS-1001 -> staff_test.
- Shared begin_staff_login does not yet set pending_started, and MFA does not enforce expiry.
- Shek still needs to register campus routes in the shared app factory.

No Colin or Shek files are included in this update. Existing real accounts and tables are untouched.

## Fresh clone to a local demo

Run from your clone on human-only. Review `git status` before pulling if you have local changes.
Use your existing virtual environment, or create one on a fresh clone:

```powershell
git clone --branch human-only https://github.com/ckoranec/devops-TheRobotProject.git
Set-Location devops-TheRobotProject
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pip install "Flask>=3.1,<4" Flask-Bcrypt pyotp "qrcode[pil]" pytest Faker
```

Flask 3.1 is required for the campus-only per-request body limit. Use the team's dependency
policy when updating its requirements file; this package does not edit that file.

### Database prerequisites

Use Colin's approved setup to create users.db, the staff users table and staff_test account,
and staff_campus_mapping with CAMPUS-1001 mapped to staff_test. Colin's initializer
now creates the tables (`python -m backend.auth.initialize_database`), but account and mapping
seeding must still use his approved setup. The initializer alone is insufficient. If these prerequisites are missing, pause database setup until Colin's
initializer/seed update is available; do not patch his tables or guess staff IDs.
No student mapping should be added. A missing mapping yields no_staff_role; invalid_signature
and expired_token are different failures, so inspect the log reason before diagnosing.

Once users.db exists, Dave's campus accounts can be seeded using hidden prompts and his helper:

```powershell
.\.venv\Scripts\python.exe -c "from getpass import getpass; from backend.auth.database import DB_FILE; from backend.auth.campus_directory import seed_campus_accounts; print('Accounts added:', seed_campus_accounts(DB_FILE, getpass('Fake campus staff password: '), getpass('Fake campus student password: ')))"
```

This adds only missing fake campus accounts and does not reset existing passwords. Store the
chosen test credentials privately. Do not delete totp.db again if your authenticator works.

### Environment variables

| Name | Purpose | Needed by |
| --- | --- | --- |
| FLASK_SECRET_KEY | Shared staff session signing | Receiver |
| CAMPUS_SSO_SIGNING_KEY | Token signing and verification; exactly the same value in both processes | Both |
| CAMPUS_IDP_COOKIE_SECRET | Separate provider session signing | Provider |
| CAMPUS_FAKE_STAFF_PASSWORD | Optional environment-driven campus seeding only | Seed helper |
| CAMPUS_FAKE_STUDENT_PASSWORD | Optional environment-driven campus seeding only | Seed helper |

All three runtime secrets must be random and at least 32 characters. The launcher generates
missing runtime secrets once and passes the same environment to both children. Existing values
are preserved and short values rejected. It does not save secrets to source or print them.
Restarting with new session keys invalidates old browser sessions; start a fresh campus login.

### Recommended independent demo launch

Close old demo servers with Ctrl+C in their original terminals. The launcher refuses occupied
ports rather than killing other processes. From the repository root:

```powershell
.\.venv\Scripts\python.exe -m campus_sso.run_demo
```

Open http://127.0.0.1:5051/campus. Sign in as campus_staff with the chosen fake campus password,
then complete the existing shared MFA. campus_student must be refused before MFA.
This launcher currently uses Dave's wrapper; it is not proof that Coty's exact entry point is done.

### Two-terminal alternative, with matching keys

Run this in terminal 1 from the repo root. It creates terminal 2 as a child, so it inherits
identical keys. Do not independently regenerate the signing key in the second terminal.

```powershell
$campusPython = (Resolve-Path '.\.venv\Scripts\python.exe').Path
foreach ($campusName in @('FLASK_SECRET_KEY','CAMPUS_SSO_SIGNING_KEY','CAMPUS_IDP_COOKIE_SECRET')) {
    $campusValue = & $campusPython -c "import secrets; print(secrets.token_urlsafe(48))"
    if ($LASTEXITCODE -ne 0) { throw 'Secret generation failed.' }
    [Environment]::SetEnvironmentVariable($campusName, ([string]$campusValue).Trim(), 'Process')
}
Start-Process powershell.exe -ArgumentList '-NoProfile', '-NoExit', '-Command', "& '$campusPython' -m campus_sso.campus_provider" -WorkingDirectory (Get-Location).Path
& $campusPython -m backend.auth.campus_staff_app
```

Terminal 2 runs the provider; terminal 1 runs the receiver. Keep both open. Stop each with Ctrl+C.
After Shek registers campus routes, the receiver command becomes `python -m backend.auth.app`.
That does not itself start the separate provider; the team must agree how its one-command demo
launcher starts both processes.

## Shared handoff contract for Colin and Shek

Mapping uses database.get_staff_id_by_campus_id(campus_id), returning a staff ID or None.
campus_routes.py now imports the shared function directly:

```python
from backend.auth.staff_login import begin_staff_login
```

The imported function is passed directly to register_staff_sso. Colin's password route calls
that same function. It clears previous authentication, sets pending_mfa_user_id and
mfa_verified=False, and returns the shared MFA redirect. No duplicate session-start code remains.
The two new handoff tests verify callable identity and equivalent pending state for both paths.

Colin's current function does not set pending_started. The campus hook can honor that field if
supplied, but does not manufacture it or claim to enforce a natural five-minute login expiry.
The existing expiry tests inject an old timestamp to expose the shared MFA enforcement gap.
Colin and Shek must agree on timestamp creation and expiry enforcement for both login paths.

Shek's factory registration, after staff and MFA registration and before returning app:

```python
from backend.auth.campus_routes import register_campus_sso
register_campus_sso(app)
```

Registration is idempotent. It does not import the shared app factory, avoiding a circular import.
Only the owner edits app.py. Blueprint-local hooks cover /campus, its child routes and the
/auth/campus endpoints. They do not intercept /login, /verify-code, /setup-2fa or /staff.
Response headers and the 16 KiB request-body limit are also campus-only.

## Timeout evidence and release gate

Scoping the old global hook exposes an existing shared-MFA gap: an expired pending session
can submit a current valid authenticator code and reach /staff. A new test demonstrates this
with disposable accounts. This is not a claim that MFA itself is bypassed; a valid code is still
required. Shared setup and verification routes must enforce pending expiry before release.
The campus timeout clears stale pending state on campus endpoints only when a timestamp exists;
the current shared login does not create that timestamp.

Two expiry tests are marked strict XFAIL, not PASS. They remain executable known-failure evidence.
Use `--runxfail` to see the failures directly. Unexpected passes cause a failure requiring review
of the markers when the owners fix expiry. Do not call this suite all-green or mark the card done.

## Verification

```powershell
.\.venv\Scripts\python.exe -m pytest backend/auth/test_campus_staff_app.py backend/auth/test_campus_sso_callback.py backend/auth/test_campus_refusal_logs.py backend/auth/test_campus_blueprint.py backend/auth/test_campus_scope.py backend/auth/test_campus_handoff.py campus_sso/test_campus_provider.py campus_sso/test_run_demo.py -v -rx
```

Tests use temporary databases and secrets. Check hostname isolation, password handoff, token
refusals, campus logging, role refusal, MFA and campus navigation. For the unresolved expiry proof:

```powershell
.\.venv\Scripts\python.exe -m pytest backend/auth/test_campus_scope.py -k shared_mfa_refuses --runxfail -v
```

Manual checks: localhost:5051/ must show Colin's form; campus entry still requires
127.0.0.1:5051/campus. Do not mix hostnames during one login because their cookies differ.
Fresh login timing remains unverified under 10 seconds. Returning-session timings are separate.
