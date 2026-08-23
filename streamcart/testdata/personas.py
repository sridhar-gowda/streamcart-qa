"""Personas — the people the scenarios are about.

A persona is a username plus a description of how the product treats that
account. Its password is resolved from the environment at the moment a
scenario needs it, and a missing password fails fast with the exact fix,
because "18 login failures" is a far worse message than one clear error.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import TYPE_CHECKING

from pydantic import SecretStr

from streamcart.core.errors import ConfigurationError
from streamcart.testdata.loader import data_file, read_mapping

if TYPE_CHECKING:
    from streamcart.core.config.models import Settings


def missing_password_message(key: str) -> str:
    return (
        f"No password configured for persona '{key}'. Copy .env.example to .env and set "
        f"STREAMCART_USERS__DEFAULT__PASSWORD (SauceDemo prints its password on the login page), "
        f"or set STREAMCART_USERS__{key.upper()}__PASSWORD for this persona only. In CI, provide it as a secret."
    )


@dataclass(frozen=True)
class Persona:
    key: str
    username: str
    description: str = ""
    password: SecretStr | None = field(default=None, repr=False, compare=False)

    @property
    def has_password(self) -> bool:
        return self.password is not None

    def with_password(self, password: SecretStr) -> Persona:
        return replace(self, password=password)

    def credentials(self) -> tuple[str, str]:
        """``(username, password)`` — raises ``ConfigurationError`` with the fix if the password is unset."""
        if self.password is None:
            raise ConfigurationError(missing_password_message(self.key))
        return self.username, self.password.get_secret_value()

    def __str__(self) -> str:
        return f"{self.key} ({self.username})"


class PersonaCatalogue:
    """The personas in ``data/users.yaml``, bound to a ``Settings`` for password resolution."""

    FILE_NAME = "users.yaml"

    def __init__(self, personas: Mapping[str, Persona], *, settings: Settings | None = None) -> None:
        self._personas = dict(personas)
        self._settings = settings

    @classmethod
    def from_file(cls, path: Path, *, settings: Settings | None = None) -> PersonaCatalogue:
        raw = read_mapping(path).get("personas") or {}
        if not isinstance(raw, Mapping):
            raise ConfigurationError(f"{path}: 'personas' must be a mapping of key -> {{username, description}}")
        personas = {
            str(key): Persona(
                key=str(key), username=str(entry["username"]), description=str(entry.get("description", ""))
            )
            for key, entry in raw.items()
        }
        return cls(personas, settings=settings)

    @classmethod
    def from_settings(cls, settings: Settings) -> PersonaCatalogue:
        return cls.from_file(data_file(settings.data_dir, cls.FILE_NAME), settings=settings)

    def keys(self) -> list[str]:
        return list(self._personas)

    def __iter__(self) -> Iterator[Persona]:
        return iter(self._personas.values())

    def __len__(self) -> int:
        return len(self._personas)

    def __contains__(self, key: object) -> bool:
        return key in self._personas

    def get(self, key: str) -> Persona:
        """The persona without its password (reference data only)."""
        try:
            return self._personas[key]
        except KeyError:
            known = ", ".join(self.keys()) or "none"
            raise ConfigurationError(
                f"Unknown persona '{key}'. Known personas: {known} (data/{self.FILE_NAME})."
            ) from None

    def resolve(self, key: str, settings: Settings | None = None) -> Persona:
        """The persona *with* its password from the environment — fails fast with the fix."""
        persona = self.get(key)
        active = settings or self._settings
        password = active.password_for(key) if active is not None else None
        if password is None:
            raise ConfigurationError(missing_password_message(key))
        return persona.with_password(password)
