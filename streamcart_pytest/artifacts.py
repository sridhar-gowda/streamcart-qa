"""Evidence capture when a test fails (or always, if configured)."""

from __future__ import annotations

from collections.abc import Callable

from streamcart.core.capabilities import Capability
from streamcart.core.config import Settings
from streamcart.core.driver.protocol import PlatformDriver
from streamcart.core.logs import get_logger
from streamcart_pytest.results import safe_name
from streamcart_pytest.stores import ArtifactStore

log = get_logger(__name__)


def capture_artifacts(driver: PlatformDriver, nodeid: str, store: ArtifactStore, settings: Settings) -> dict[str, str]:
    """Screenshot, page source and console log for ``nodeid``; each guarded so a dead session
    can never mask the real failure. Returns ``{name: location}``."""
    captured: dict[str, str] = {}
    base = safe_name(nodeid)
    policy = settings.artifacts

    if policy.screenshot and driver.supports(Capability.SCREENSHOT):
        _try(
            captured,
            "screenshot",
            lambda: store.put(f"{base}/screenshot.png", driver.screenshot(), content_type="image/png"),
        )
    if policy.page_source and driver.supports(Capability.PAGE_SOURCE):
        suffix = "html" if driver.platform.is_web else "xml"
        _try(
            captured,
            "page_source",
            lambda: store.put(
                f"{base}/page_source.{suffix}", driver.page_source().encode("utf-8"), content_type="text/plain"
            ),
        )
    if policy.console_logs:
        _try(captured, "console_log", lambda: _put_console_log(driver, store, base))
    return captured


def _put_console_log(driver: PlatformDriver, store: ArtifactStore, base: str) -> str | None:
    lines = driver.console_logs()
    if not lines:
        return None
    return store.put(f"{base}/console.log", "\n".join(lines).encode("utf-8"), content_type="text/plain")


def _try(captured: dict[str, str], name: str, action: Callable[[], str | None]) -> None:
    try:
        location = action()
    except Exception as exc:  # evidence is best-effort; the failure being reported matters more
        log.warning("Could not capture %s: %s", name, exc)
        return
    if location:
        captured[name] = location
