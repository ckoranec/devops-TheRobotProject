import os
import secrets


def resolve_secret(name: str, *, allow_ephemeral: bool = False) -> str:
    """Read a >=32-char secret from env; fail with clear guidance if missing."""
    value = os.environ.get(name, "")
    if len(value) >= 32:
        return value

    if os.environ.get("APP_ENV") == "production":
        raise RuntimeError(
            f"Set {name} to a random value of at least 32 characters in your environment."
        )

    if allow_ephemeral:
        generated = secrets.token_hex(32)
        os.environ[name] = generated
        print(
            f"WARNING: {name} not set. Generated a temporary key for this process only; "
            f"set {name} (>=32 chars) in your environment if another process needs the same key."
        )
        return generated

    raise RuntimeError(
        f"Missing or invalid {name} (must be at least 32 characters). "
        f"Export the same {name} in both the app (:5051) and provider (:5052) environments "
        "before running `python -m backend.auth.app`."
    )