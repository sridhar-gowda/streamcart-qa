"""Repository-level pytest configuration.

The execution platform (``streamcart_pytest.plugin``) registers itself through
the ``pytest11`` entry point when the package is installed (``pip install -e .``).
For a bare source checkout we register it here instead — but never twice,
because pytest refuses duplicate plugin registration.

Step-definition modules are registered as plugins so their steps are available
to every feature file, wherever the feature's test module lives.

``pytester`` is pytest's own plugin for testing plugins; the framework
self-tests in ``tests/framework`` use it to run the StreamCart plugin in an
isolated session.
"""

from importlib.metadata import entry_points

STEP_MODULES = [
    "tests.steps.common_steps",
    "tests.steps.session_steps",
    "tests.steps.inventory_steps",
    "tests.steps.cart_steps",
    "tests.steps.checkout_steps",
]


def _registered_via_entry_point() -> bool:
    return any(ep.value.startswith("streamcart_pytest.plugin") for ep in entry_points(group="pytest11"))


pytest_plugins = ["pytester", *STEP_MODULES] + ([] if _registered_via_entry_point() else ["streamcart_pytest.plugin"])
