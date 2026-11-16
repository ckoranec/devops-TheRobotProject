import logging
import os
import secrets
from flask import Flask

from staff_login import staff_bp
from .mfa import mfa_bp, init_totp_db
from campus_login import campus_bp
try:
    from .password_hashing import verify_password
except ImportError:
    from password_hashing import verify_password

