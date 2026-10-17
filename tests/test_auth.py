import pytest

from backend.auth import User


def test_password_hashing():
    user = User()
    user.set_password("SecurePassword2026!")
    assert user.password_hash != "SecurePassword2026!"
    assert user.check_password("SecurePassword2026!")
    assert not user.check_password("IncorrectPassword")


def test_short_password_rejected():
    user = User()
    with pytest.raises(ValueError):
        user.set_password("short")


def test_customer_role_default():
    user = User()
    assert user.is_staff() is False


def test_staff_role():
    user = User()
    user.role = "staff"
    assert user.is_staff() is True
