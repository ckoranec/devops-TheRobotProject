# Campus SSO setup and integration — David Noyes, 2026-11-18

## Status and ownership

This is an intermediate campus-scope correction, not a completed authentication release.
Campus routes are one `campus` blueprint; helpers, tests and launchers do not need blueprints.
The provider stays a separate service on 5052. The receiving shared app runs on 5051.
No teammate source files or real database tables are changed by this update.

Integration checked against human-only commit 7933e98a5499fca90f36301aff0a135b76193b3f:
- Campus now directly imports Colin's staff_login.begin_staff_login(staff_id).
- The duplicate campus session-start function has been removed; there is no fallback copy.
- Colin's initializer now calls create_staff_campus_mapping().
- Mapping lookup still imports and uses Colin's database functions.
- The initializer creates the mapping table, but does not itself seed CAMPUS-1001 -> staff_test.
- Shared begin_staff_login does not yet set pending_started, and MFA does not enforce expiry.
- Shek has registered campus routes in the shared app factory (commit 7933e98).
- The shared factory also initializes campus/mapping tables, but still needs an existing users database.

No Colin or Shek files are included in this update. Existing real accounts and tables are untouched.

## Remembered provider login (2026-11-19)

The provider now remembers campus authentication in a server-side, single-process store.
The browser keeps only an opaque HttpOnly/SameSite=Lax session ID cookie. A returning
request gets a fresh state-bound 60-second token without asking for the campus password.
Staff mapping and fresh staff MFA remain required. Sessions expire after 15 minutes idle
or one hour total and are revoked on provider logout, restart, account deletion, or password
change. These are explicit local-demo defaults for team review.

Use http://127.0.0.1:5052/logout to sign out of the provider. Staff logout is separate.
For full checklist status, reproducible log evidence, timing worksheet and answers to Coty's
cleanup/comment questions, read CAMPUS_CARD_STATUS.md. Under-10-second fresh login and the
shared-owner dependencies are not marked complete.

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
This launcher uses Dave's thin wrapper around Shek's shared factory. The factory now registers campus itself; repeat registration is safely ignored. The integration tests exercise the shared factory directly.

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
& $campusPython -m backend.auth.app
```

Terminal 2 runs the provider; terminal 1 runs the receiver. Keep both open. Stop each with Ctrl+C.
The receiver command is now `python -m backend.auth.app`. This starts the unified staff
application, not the separate provider. Dave's run_demo starts both services with matching
keys; the two-terminal sequence above verifies Coty's exact shared entry point.

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

Shek's factory now contains this registration after staff and MFA registration:

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
.\.venv\Scripts\python.exe -m pytest backend/auth/test_campus_staff_app.py backend/auth/test_campus_sso_callback.py backend/auth/test_campus_refusal_logs.py backend/auth/test_campus_blueprint.py backend/auth/test_campus_scope.py backend/auth/test_campus_handoff.py backend/auth/test_campus_card_evidence.py campus_sso/test_campus_provider.py campus_sso/test_run_demo.py campus_sso/test_provider_sessions.py campus_sso/test_config.py backend/auth/test_campus_registration_config.py -v -rx
```

Tests use temporary databases and secrets. Check hostname isolation, password handoff, token
refusals, campus logging, role refusal, MFA and campus navigation. For the unresolved expiry proof:

```powershell
.\.venv\Scripts\python.exe -m pytest backend/auth/test_campus_scope.py -k shared_mfa_refuses --runxfail -v
```

Manual checks: localhost:5051/ must show Colin's form; campus entry still requires
127.0.0.1:5051/campus. Do not mix hostnames during one login because their cookies differ.
Fresh login timing remains unverified under 10 seconds. Returning-session timings are separate.

## Shared secret interface for Abhishek (2026-11-19)

All active campus secret loading lives in `campus_sso/config.py`. Importing it
neither starts a server nor reads or generates secrets. The functions read at
startup, so set environment variables before calling the app factory.

- `read_secret(name, environ=None)` validates a required value without printing it.
- `load_staff_config(environ=None)` returns Flask `SECRET_KEY` from
  `FLASK_SECRET_KEY`, plus `CAMPUS_SSO_SIGNING_KEY`.
- `load_provider_config(environ=None)` returns Flask `SECRET_KEY` from
  `CAMPUS_IDP_COOKIE_SECRET`, plus the same signing variable.
- `make_demo_environment(source)` copies the environment, preserves configured
  values, generates missing demo values once, and passes them to both children.
  Separate terminals must receive the SAME signing value; never generate it
  independently in each terminal. Restart both services together after rotation.

Optional explicit-config interface for the owner (the current factory already works via the environment fallback):

```python
from campus_sso.config import load_staff_config
from backend.auth.campus_routes import register_campus_sso

# After constructing app, before serving requests:
app.config.update(load_staff_config())
# Keep the owner's existing staff and MFA blueprint registration.
register_campus_sso(app)
# Return app as usual.
```

This is an integration excerpt for the owner, not a replacement for `app.py`.
Configure the shared session key once; remove/avoid any later assignment that
would replace it. Dave's independent wrapper already performs these steps.
The receiver takes `CAMPUS_SSO_SIGNING_KEY` from `app.config` when configured.
Only when absent does it load the environment variable. Invalid explicit
configuration fails startup rather than silently falling back. Registration
never changes the shared app session secret.
All three staff blueprints share ONE Flask application/session configuration.
Blueprints do not each need a secret, and database/helper/test modules do not
need to load secrets unless they use them.

The provider is a separate app and uses `load_provider_config()`. Keep its cookie
secret separate from the staff cookie secret. The signing key must match across
provider and receiver. Use independently generated random values of at least
32 characters; do not commit them or put them in a teammate message.
`make_token(signer, identity, state)` stays unchanged: its supplied signer is
constructed from the validated signing key. It does not fetch session secrets.

Existing imports of `read_secret` from `campus_sso.campus_provider` remain
compatible and refer to the central implementation. Historical standalone demo
variables (`CAMPUS_DEMO_SECRET`, `CAMPUS_DEMO_COOKIE_SECRET`) are not required by
the active unified flow. Campus account seed passwords remain separate from all
cryptographic keys.

This configuration does not grant MFA success. A still-valid verified staff
session can continue to `/staff`; a fresh staff login still uses Colin's
`begin_staff_login` and Shek's MFA. Provider remembrance skips only the campus
password prompt. Shared pending-MFA expiry remains an owner dependency.

## Registration configuration hand-off (2026-11-19)

Registration is now present in Shek's app.py. His ensure_secret helper populates the environment and campus registration reads it. No further owner edit is required for the current connection. If the owner later chooses explicit configuration, the supported interface is:

```python
from campus_sso.config import load_staff_config
from backend.auth.campus_routes import register_campus_sso

# Inside the existing shared factory, after Flask app construction:
app.config.update(load_staff_config())
# Keep the existing staff/MFA registration and other factory initialization.
register_campus_sso(app)
```

This excerpt is for the owner to place in app.py, not a replacement file.
Dave's wrapper already loads this configuration and registers the campus routes.
The campus blueprint forwards the configured signing key to its token validator.
Colin's actual get_staff_id_by_campus_id and begin_staff_login remain in use.
The separate provider must receive the same signing value in its environment.
Do not rotate keys on every request; restart both services together after rotation.

A remembered provider login immediately reaches staff MFA without displaying a
campus password form. This is expected. To choose another campus account, use
provider logout at http://127.0.0.1:5052/logout and confirm logout, then start a
new request at http://127.0.0.1:5051/campus. Do not reload an old token callback.
The Continue button is only for an existing verified staff session; it does not
mark a fresh login as MFA-verified. Shared pending-MFA expiry is still unresolved.

## Integration test isolation after Shek's factory update

The shared factory imports DB_FILE into its own module. Tests must point BOTH
that imported path and database.DB_FILE to their temporary database. This update
changes only Dave's test fixture, not the shared factory or anyone's real database.
The main campus integration suite now calls backend.auth.app.create_app directly.
Configuration-specific tests construct an isolated Flask app with the real shared
blueprints before registration, so they actually test key selection at registration
time rather than after an already-registered callback.

## Coty's ownership and completion decisions

David: shared handoff, provider remembrance, live Verify demonstrations, campus
logs, fresh-clone instructions, and separately labelled timing measurements.
Colin: staff 15-minute idle timeout, staff attempt logging/password tests, and
CAMPUS-1001 -> staff_test seed. Shek: shared integration, now registered.
Jeremy: account lockout and password policy. Satchi: recovery blueprint/pages.
Do not add these owners' implementations to campus hooks. Pending-MFA expiry
is a separate shared-flow gap, not the provider's idle timeout or the staff idle
timeout. Report its two expected failures for shared-owner assignment.

Do not mark the card complete until a fresh clone is demonstrated with approved
staff seed/mapping, all Verify evidence is shown, timings are measured, and Coty
resolves customer-order access versus staff-only acceptance scope.
