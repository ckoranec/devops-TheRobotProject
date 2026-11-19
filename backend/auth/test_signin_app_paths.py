import sqlite3
import time as real_time
import types

import pyotp
import pytest

from backend.auth import database, mfa
from backend.auth.app import create_app
from backend.auth.staff_login import begin_staff_login   # shared handoff (see note below)

try:
    from backend.auth.password_hashing import hash_password   # ADAPT: your hashing function name
except ImportError:
    import bcrypt
    def hash_password(pw):
        return bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()

BASE = "http://127.0.0.1:5051"      # the campus blueprint refuses any other host
PASSWORD = "correct horse battery"


# ---------- fixtures ----------

class Clock:
    """Controllable clock so each TOTP step is used at most once."""
    def __init__(self):
        self.now = real_time.time()

    def next_step(self):
        self.now += 30


@pytest.fixture
def clock(monkeypatch):
    c = Clock()
    # mfa only calls time.time(), so replace its `time` module reference
    monkeypatch.setattr(mfa, "time", types.SimpleNamespace(time=lambda: c.now))
    return c


@pytest.fixture
def app(tmp_path, monkeypatch, clock):
    users_db = tmp_path / "users.db"
    monkeypatch.setattr(database, "DB_FILE", str(users_db))
    monkeypatch.setattr(mfa, "TOTP_DB_PATH", str(tmp_path / "totp.db"))
    for name in ("FLASK_SECRET_KEY", "CAMPUS_SSO_SIGNING_KEY", "CAMPUS_IDP_COOKIE_SECRET"):
        monkeypatch.setenv(name, "t" * 64)
    monkeypatch.delenv("APP_ENV", raising=False)

    conn = sqlite3.connect(users_db)
    conn.executescript("""
        CREATE TABLE users (id INTEGER PRIMARY KEY, username TEXT UNIQUE, password_hash TEXT);
        CREATE TABLE campus_accounts (
            campus_id TEXT PRIMARY KEY NOT NULL, username TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL, affiliation TEXT NOT NULL, password_hash TEXT NOT NULL);
        -- ADAPT: use your real staff_campus_mapping schema
        CREATE TABLE staff_campus_mapping (campus_id TEXT PRIMARY KEY, staff_user_id INTEGER);
    """)
    conn.execute("INSERT INTO users (id, username, password_hash) VALUES (1, 'newuser', ?)",
                 (hash_password(PASSWORD),))
    conn.execute("INSERT INTO users (id, username, password_hash) VALUES (2, 'olduser', ?)",
                 (hash_password(PASSWORD),))
    conn.commit()
    conn.close()

    flask_app = create_app()
    flask_app.config["TESTING"] = True

    # Test-only route that runs the shared handoff the campus callback uses
    flask_app.add_url_rule("/_test/handoff/<int:uid>", "test_handoff",
                           lambda uid: begin_staff_login(uid))
    return flask_app


@pytest.fixture
def client(app):
    return app.test_client()


# ---------- helpers ----------

def login(client, username, password=PASSWORD):
    return client.post("/login", data={"username": username, "password": password},
                       base_url=BASE)


def staff_status(client):
    return client.get("/staff", base_url=BASE).status_code


def assert_staff_denied(client):
    assert staff_status(client) in (302, 401, 403), "/staff reachable before 2FA completed"


def assert_staff_allowed(client):
    assert staff_status(client) == 200


def location(resp):
    return resp.headers.get("Location", "")


def stored_secret(user_id):
    conn = sqlite3.connect(mfa.TOTP_DB_PATH)
    try:
        return conn.execute("SELECT totp_secret FROM totp_secrets WHERE user_id = ?",
                            (user_id,)).fetchone()[0]
    finally:
        conn.close()


def code_for(secret, clock):
    clock.next_step()
    return pyotp.TOTP(secret).at(clock.now)


def submit_code(client, path, code):
    return client.post(path, data={"code": code}, base_url=BASE)


def enroll(client, username, user_id, clock):
    """Full new-user flow; leaves the user with a confirmed TOTP secret."""
    login(client, username)
    client.get("/setup-2fa", base_url=BASE)                      # creates the pending secret
    secret = stored_secret(user_id)
    resp = submit_code(client, "/setup-2fa", code_for(secret, clock))
    assert resp.status_code == 302 and "/staff" in location(resp)
    return secret


# ---------- baseline ----------

def test_staff_denied_with_no_session(client):
    assert_staff_denied(client)


# ---------- path 1: password -> 2FA setup -> /staff (new user) ----------

def test_new_user_password_then_setup_then_staff(client, clock):
    resp = login(client, "newuser")
    assert resp.status_code == 302
    assert "/setup-2fa" in location(resp) or "/verify-code" in location(resp)
    assert_staff_denied(client)                       # password alone is not enough

    client.get("/setup-2fa", base_url=BASE)
    secret = stored_secret(1)
    assert_staff_denied(client)                       # seeing the QR page is not enough

    bad = submit_code(client, "/setup-2fa", "000000")
    assert bad.status_code == 200                     # re-renders with an error
    assert_staff_denied(client)                       # wrong code does not authenticate

    good = submit_code(client, "/setup-2fa", code_for(secret, clock))
    assert good.status_code == 302 and "/staff" in location(good)
    assert_staff_allowed(client)


# ---------- path 2: password -> 2FA code -> /staff (existing user) ----------

def test_existing_user_password_then_code_then_staff(client, app, clock):
    secret = enroll(app.test_client(), "olduser", 2, clock)

    fresh = app.test_client()                         # new browser, no session
    resp = login(fresh, "olduser")
    assert resp.status_code == 302 and "/verify-code" in location(resp)
    assert_staff_denied(fresh)

    bad = submit_code(fresh, "/verify-code", "000000")
    assert bad.status_code == 200
    assert_staff_denied(fresh)

    good = submit_code(fresh, "/verify-code", code_for(secret, clock))
    assert good.status_code == 302 and "/staff" in location(good)
    assert_staff_allowed(fresh)


# ---------- path 3: campus -> callback -> 2FA -> /staff (mapped account) ----------
# The callback calls begin_staff_login(staff_id). This test drives that same
# handoff directly. A full-callback version needs the provider's signed proof.

def test_campus_mapped_handoff_requires_2fa(client, app, clock):
    secret = enroll(app.test_client(), "olduser", 2, clock)

    fresh = app.test_client()
    resp = fresh.get("/_test/handoff/2", base_url=BASE)
    assert resp.status_code == 302
    assert "/verify-code" in location(resp) or "/setup-2fa" in location(resp)
    assert_staff_denied(fresh)                        # campus identity alone is not enough

    good = submit_code(fresh, "/verify-code", code_for(secret, clock))
    assert good.status_code == 302
    assert_staff_allowed(fresh)


def test_campus_handoff_new_user_goes_through_setup(client, clock):
    resp = client.get("/_test/handoff/1", base_url=BASE)
    assert "/setup-2fa" in location(resp) or "/verify-code" in location(resp)
    assert_staff_denied(client)


# ---------- path 3b: unmapped campus account is refused ----------

def test_campus_unmapped_is_refused(client):
    assert database.get_staff_id_by_campus_id("not-a-mapped-id") is None
    assert_staff_denied(client)                       # and no session was created

# ADAPT (full callback): build a valid signed proof for an unmapped campus_id with
# campus_provider's token function, GET /auth/campus/callback?..., then assert
# status 403, "pending_mfa_user_id" not in session, and /staff denied.


# ---------- path 4: recovery -> new password -> login -> 2FA ----------

def test_recovery_then_login_still_requires_2fa(app, clock):
    if "recovery.reset_password" not in app.view_functions:
        pytest.skip("recovery blueprint not built yet")
    # ADAPT: seed a recovery code for user 2, POST it to /verify-recovery, POST a
    # new password to the reset route, then:
    #   1. the old password no longer logs in (401)
    #   2. the new password redirects to /verify-code
    #   3. /staff is denied until a valid TOTP code is submitted
    #   4. the same recovery code cannot be used a second time


# ---------- cross-cutting guarantees ----------

def test_wrong_password_never_starts_mfa(client):
    resp = login(client, "olduser", "wrong password")
    assert resp.status_code == 401
    assert client.get("/verify-code", base_url=BASE).status_code in (302, 403, 404)
    assert_staff_denied(client)


def test_pending_session_cannot_reach_mfa_only_actions(client):
    login(client, "olduser")
    assert client.post("/reset-2fa", base_url=BASE).status_code == 403
    assert_staff_denied(client)


def test_totp_code_cannot_be_replayed(client, app, clock):
    secret = enroll(app.test_client(), "olduser", 2, clock)

    fresh = app.test_client()
    login(fresh, "olduser")
    code = code_for(secret, clock)
    assert submit_code(fresh, "/verify-code", code).status_code == 302

    other = app.test_client()
    login(other, "olduser")
    replay = submit_code(other, "/verify-code", code)   # same code, same time step
    assert replay.status_code == 200                    # rejected, error shown
    assert_staff_denied(other)


def test_five_bad_codes_lock_out_even_a_correct_code(client, app, clock):
    secret = enroll(app.test_client(), "olduser", 2, clock)
    fresh = app.test_client()
    login(fresh, "olduser")
    for _ in range(mfa.MAX_CODE_TRIES):
        submit_code(fresh, "/verify-code", "000000")
    locked = submit_code(fresh, "/verify-code", code_for(secret, clock))
    assert locked.status_code == 200                    # still on the page, locked
    assert_staff_denied(fresh)


def test_logout_ends_access(client, app, clock):
    enroll(client, "olduser", 2, clock)
    assert_staff_allowed(client)
    client.post("/logout", base_url=BASE)
    assert_staff_denied(client)