# Staff login (Authenticate board)

All auth code lives in this folder, one file per card.

## Setup (once per laptop)

From the repo root:

```
pip install -r requirements.txt
python backend/auth/seed_users.py
```

This creates `backend/auth/users.db` with a fixed test user plus 15 random fake users (their passwords print once, in the terminal).

- Test login: `staff_test` / `Robot-Test-2026!` (simulated account, local only)
- Need a fresh database? Delete `users.db` and run the seed script again.
- `*.db` files are ignored by Git. Never commit one.
- `db_check_simulation.py` is a quick self-test. It uses its own `test_users.db` and deletes it each run, so it never touches `users.db`.

## Rules
- Hash passwords only with the shared Flask-Bcrypt function (Card 1). Never store or log a plain password.
- No secrets or keys in Git. If one gets pushed, tell Coty right away.


## Card 4 — Fake campus account setup

Updated: 2026-11-13 — David Noyes

This is simulated university authentication, not a real campus SSO connection.

Campus accounts live in the `campus_accounts` table inside the existing
`backend/auth/users.db`. Staff accounts remain in `users`.

Do not delete an existing database or rerun the staff seed script merely to add
campus accounts.

### Setup environment variables

Supply these values locally before seeding:

- `CAMPUS_FAKE_STAFF_PASSWORD` — Initial password for `campus_staff`.
- `CAMPUS_FAKE_STUDENT_PASSWORD` — Initial password for `campus_student`.

Use fake, local-only passwords. Never commit their values or print them in logs.
The setup function stores bcrypt hashes using the shared password-hashing module.

From the repository root, with those variables set and `users.db` already present:

```powershell
# Add missing campus accounts without resetting existing accounts.
.\.venv\Scripts\python.exe -c "from backend.auth.database import DB_FILE; from backend.auth.campus_directory import seed_campus_accounts_from_environment; print('New campus accounts added:', seed_campus_accounts_from_environment(DB_FILE))"
```

Initial accounts:

| Campus ID | Username | Affiliation |
|---|---|---|
| CAMPUS-1001 | campus_staff | staff |
| CAMPUS-2001 | campus_student | student |

Running setup again preserves existing campus accounts and passwords.
Changing an environment variable does not reset an existing account's password.

Remove the setup password variables after use. The database lookup checks saved
hashes and does not require those variables for normal authentication.

### Lookup and authorization

`find_campus_identity(username, password)` opens the database read-only and checks
only `campus_accounts`. It returns campus identity fields or `None` for invalid
credentials. Missing databases or tables are setup errors.

Campus authentication does not grant staff access. The staff application must map
the permanent campus ID to an authorized staff user and use the shared login/MFA
process.

### Provider environment variables

The separate provider uses these additional variable names:

- `CAMPUS_IDP_COOKIE_SECRET` — Provider session-cookie signing secret.
- `CAMPUS_SSO_SIGNING_KEY` — Token signing key shared with the staff receiver.

The current provider requires these secrets to be random values of at least
32 characters. Keep their values out of Git.

Colin's staff application also requires `FLASK_SECRET_KEY` for its session cookies.
Use a separate cookie secret for each application.

### Tests and integration status

```powershell
# Run campus-directory tests using temporary databases.
.\.venv\Scripts\python.exe -m pytest backend/auth/campus_directory.py -v
```

Database setup and lookup are implemented. Switching the separate provider to the
database lookup and completing shared staff-session, role, and logging integration
are subsequent steps. Seeding accounts alone does not complete browser SSO.