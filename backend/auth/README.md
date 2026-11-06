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
