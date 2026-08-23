"""Platform adapters — the containment layer.

This is the only package in the codebase permitted to import Selenium, Appium
or an ECP client (enforced by ruff ``banned-api`` per-file-ignores). Each module
defines one driver and registers it::

    from streamcart.core.driver.base import BaseDriver
    from streamcart.core.driver.registry import register_platform
    from streamcart.core.platform import Platform

    @register_platform(Platform.ROKU)
    class RokuEcpDriver(BaseDriver):
        capabilities = FAMILY_BASELINE[PlatformFamily.TV] - {Capability.PAGE_SOURCE}
        ...

To add a platform: add a module here (or ship one via the ``streamcart.platforms``
entry-point group), add a ``config/platform/<name>.yaml`` and a target file.
Nothing else changes.

Library imports that are optional (Appium) must happen lazily inside methods,
so that discovery never fails on a machine that only has the Web stack installed.
"""
