# Adding a platform

Adding a platform means creating new files. You do not edit anything in `streamcart/core`,
`streamcart/ui`, `streamcart/screenplay` or `streamcart_pytest`. Here is why that works:

- the driver registry finds adapters by itself (it scans the adapters package),
- the configuration loader finds YAML layers by name,
- locators already carry selectors per platform *family* (web / mobile / tv),
- the pytest plugin turns any `@<platform-name>` tag into a marker automatically.

There is a test that does all of the steps below with a made-up platform and checks that
everything resolves:
`tests/framework/test_architecture.py::test_adding_a_platform_requires_new_files_only`.

The example below adds **Roku** as if it did not exist yet. The real adapter,
`streamcart/core/driver/adapters/roku_ecp.py`, is the reference to copy from.

## Step 1 — the adapter: `streamcart/core/driver/adapters/roku_ecp.py`

```python
from streamcart.core.capabilities import Capability
from streamcart.core.driver.base import BaseDriver
from streamcart.core.driver.focus import FocusNavigator
from streamcart.core.driver.protocol import Element, Key
from streamcart.core.driver.registry import register_platform
from streamcart.core.locators import Locator
from streamcart.core.platform import Platform, PlatformFamily

# The name "roku" is what people type on the command line (--platform roku),
# the config folder name (config/platform/roku.yaml), the Gherkin tag (@roku)
# and the locator key (roku=By...).
ROKU = Platform("roku", PlatformFamily.TV, default_target="roku-lab")


@register_platform(ROKU)
class RokuEcpDriver(BaseDriver):
    """Roku channel driven over the External Control Protocol (HTTP on port 8060)."""

    capabilities = frozenset(
        {
            Capability.DPAD,
            Capability.FOCUS_NAVIGATION,
            Capability.DEEP_LINK,
            Capability.HARDWARE_BACK,
            Capability.SCREENSHOT,
            Capability.PAGE_SOURCE,
        }
    )

    def start(self) -> None: ...  # open the session (for Roku: check the device answers on ECP)
    def stop(self) -> None: ...
    def open(self, destination: str) -> None: ...  # POST /launch/<channel>?contentId=<destination>
    def current_location(self) -> str: ...  # GET /query/active-app
    def find(self, locator: Locator, *, timeout=None) -> Element: ...  # GET /query/app-ui -> SceneGraph XML
    def find_all(self, locator: Locator, *, timeout=None) -> list[Element]: ...
    def is_present(self, locator: Locator, *, timeout=0.0) -> bool: ...
    def press(self, key: Key) -> None: ...  # POST /keypress/<Key>
    def screenshot(self) -> bytes: ...
    def page_source(self) -> str: ...
```

What `BaseDriver` gives you for free:

- `supports()` and `require()`, based on the `capabilities` you declared (a class attribute; override `declared_capabilities()` when one adapter serves several platforms);
- `self.wait`, a condition-based waiter with the configured timeouts;
- default `hover`, `swipe`, `long_press` and `console_logs` that raise a clear
  `CapabilityNotSupportedError`. Override them only if you also declare the capability.

**TV platforms and "select".** On a television there is no pointer. `element.select()` means
"move the focus onto me with the d-pad, then press OK". Do not write that algorithm again:
`FocusNavigator` already has it. Your adapter only provides three small pieces — where the focus
is right now, how to press a direction, and how to let the screen settle. The algorithm is
unit-tested without a device in `tests/framework/test_focus.py`.

**Raise the framework's own errors.** `ElementNotFoundError`, `ElementNotInteractableError`,
`DriverSessionError` and `AppUnreachableError` (from `streamcart.core.errors`) are how the
execution platform knows whether a failure is a UI-contract problem or an environment problem —
and whether to retry it.

**Only adapters may import automation libraries.** Selenium, Appium and HTTP clients are
banned everywhere else (ruff `banned-api` and import-linter enforce it). If the library is
optional, import it inside `start()` like `appium_mobile.py` does, so the web suite installs
without it.

## Step 2 — two YAML files

`config/platform/roku.yaml` — settings that are true for every Roku run:

```yaml
tv:
  ecp_port: 8060
  channel_id: dev
  keypress_delay: 0.2
timeouts:
  default: 20          # ECP query + render round-trips are slow
  focus_settle: 0.5
```

`config/target/roku-lab.yaml` — *where* it runs (the platform's `default_target`):

```yaml
tv:
  ecp_host: 192.168.10.50
```

Settings are validated. An unknown key is an error, not a silent default. If the platform needs
a setting that does not exist yet, add a field to the matching settings model — that is the one
case that touches existing code, and it only adds.

## Step 3 — locators: usually nothing to do

`Locator.test_id(...)` and the `tv=` family key already resolve for a new TV platform. Add a
platform-specific selector only where the platform really differs:

```python
CHECKOUT = Locator.define(
    "checkout button",
    web=By.TEST_ID("checkout"),
    mobile=By.ACCESSIBILITY_ID("checkout"),
    tv=By.TEXT("Checkout"),
    roku=By.XPATH("//Button[@name='checkout']"),
)
```

## Step 4 — Gherkin: the tag already works

Put `@roku` on a scenario to run it only there; put `@requires:dpad` on a scenario to skip it on
platforms without a d-pad. To see what a Roku run would contain today:

```bash
pytest --platform roku --collect-only -q
```

## Optional — ship the adapter as its own package

Declare an entry point in that package's `pyproject.toml`; the registry imports it:

```toml
[project.entry-points."streamcart.platforms"]
roku = "streamcart_roku.driver"
```

## Checklist

- [ ] The adapter declares `Platform(...)`, extends `BaseDriver` and has `@register_platform`.
- [ ] `config/platform/<name>.yaml` and `config/target/<default_target>.yaml` exist
      (`test_every_registered_platform_ships_its_config_layers` checks this).
- [ ] Declared capabilities match implemented methods
      (`test_declared_but_unimplemented_capability_fails_loudly` checks this).
- [ ] `pytest tests/framework` is green, and `pytest --platform <name> --collect-only` shows the
      scenarios you expect.
