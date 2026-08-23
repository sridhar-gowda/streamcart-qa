"""The UI model: Pages and Components.

This layer knows *where things are and how to touch them* — nothing more.

What belongs here
    - ``Locator`` declarations (every platform's selector for one element)
    - element primitives: press a button, type into a field, read a label
    - typed reads: a price as ``Decimal``, a badge count as ``int``
    - composition: a Page is made of Components, a Component of smaller ones

What never belongs here
    - multi-step workflows ("log in and add a product") → ``screenplay.tasks``
    - expectations or assertions → step definitions
    - anything platform-specific beyond a locator key → ``core.driver.adapters``

Everything talks to the ``PlatformDriver`` protocol; Selenium never appears.
"""

from streamcart.ui.base import Component, Page

__all__ = ["Component", "Page"]
