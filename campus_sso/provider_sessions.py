# 2026-11-19 - David Noyes - Single-process local provider sessions.
import hashlib
from contextlib import closing
import secrets
import sqlite3
import threading
import time
from pathlib import Path

IDLE_SECONDS = 15 * 60
MAX_SECONDS = 60 * 60
COOKIE_NAME = 'maxbytes_campus_sso'


def current_identity(campus_id, database_path=None):
    """Read existing identity and a credential-change fingerprint; never seed data."""
    if database_path is None:
        from backend.auth.database import DB_FILE
        database_path = DB_FILE
    with closing(sqlite3.connect(Path(database_path).resolve().as_uri() + '?mode=ro', uri=True)) as conn:
        row = conn.execute(
            'SELECT campus_id, username, name, affiliation, password_hash FROM campus_accounts WHERE campus_id = ?',
            (campus_id,),
        ).fetchone()
    if row is None:
        return None
    identity = dict(zip(('campus_id', 'username', 'name', 'affiliation'), row[:4]))
    fingerprint = hashlib.sha256(str(row[4]).encode()).hexdigest()
    return identity, fingerprint


class ProviderSessions:
    """Opaque browser IDs refer to memory-only records. Restart revokes all sessions."""
    def __init__(self, clock=time.monotonic, capacity=1000):
        self.clock = clock
        self.capacity = capacity
        self.records = {}
        self.lock = threading.RLock()

    def expired(self, record, now):
        return now - record['seen'] >= IDLE_SECONDS or now - record['created'] >= MAX_SECONDS

    def create(self, identity, fingerprint, previous=None):
        with self.lock:
            now = self.clock()
            self.records.pop(previous, None)
            for key, value in list(self.records.items()):
                if self.expired(value, now):
                    del self.records[key]
            if len(self.records) >= self.capacity:
                raise RuntimeError('Provider session capacity reached')
            session_id = secrets.token_urlsafe(32)
            self.records[session_id] = {'campus_id': identity['campus_id'], 'fingerprint': fingerprint,
                                        'created': now, 'seen': now}
            return session_id

    def lookup(self, session_id, database_path=None):
        with self.lock:
            record = self.records.get(session_id)
            if record is None:
                return None, 'session_invalid'
            now = self.clock()
            if self.expired(record, now):
                del self.records[session_id]
                return None, 'session_expired'
            current = current_identity(record['campus_id'], database_path)
            if current is None or not secrets.compare_digest(current[1], record['fingerprint']):
                del self.records[session_id]
                return None, 'session_revoked'
            record['seen'] = now
            return current[0], 'session_reused'

    def revoke(self, session_id):
        with self.lock:
            self.records.pop(session_id, None)
