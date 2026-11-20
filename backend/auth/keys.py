import os
import secrets


def resolve_secret(name: str, *, allow_ephemeral: bool = True) -> str:
    """Resolve a >=32-char secret from env, or generate one in memory for dev."""
    value = os.environ.get(name, "")
    if len(value) >= 32:
        return value

    if os.environ.get("APP_ENV") == "production":
        raise RuntimeError(
            f"Set {name} to a random value of at least 32 characters in your environment."
        )

    if not allow_ephemeral:
        raise RuntimeError(
            f"Missing or invalid {name} (must be at least 32 characters). "
            f"Export {name} in your environment before starting."
        )

    generated = secrets.token_hex(32)
    os.environ[name] = generated
    print(f"WARNING: {name} not set. Generated temporary in-memory key for this process.")
    return generated