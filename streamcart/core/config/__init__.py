"""Configuration: layered YAML + environment, resolved once per session.

    pydantic defaults
     ← config/base.yaml
     ← config/platform/<platform>.yaml
     ← config/target/<target>.yaml      (where it runs: local Chrome, grid, device lab …)
     ← config/env/<env>.yaml            (what it runs against: dev, staging, prod)
     ← config/local.yaml                (gitignored personal overrides)
     ← .env                             (gitignored local secrets)
     ← process environment              (CI: GitHub Secrets / vars)
     ← CLI flags                        (--platform, --env, --target, --base-url, --headed …)

Secrets are never read from YAML. See ``.env.example`` for every variable name.
"""

from streamcart.core.config.loader import load_settings
from streamcart.core.config.models import Settings

__all__ = ["Settings", "load_settings"]
