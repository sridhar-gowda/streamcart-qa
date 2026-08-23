"""StreamCart QA — a multi-platform test automation framework.

Layers (top depends on bottom, never the reverse):

    features/               Gherkin — business language, platform-agnostic
    tests/steps/            step definitions — one line each, delegate to Screenplay
    streamcart.screenplay   Actors, Abilities, Tasks, Questions — business intent
    streamcart.ui           Pages and Components — locators + element primitives
    streamcart.core         Driver protocol, adapters, config, waits, errors

The execution platform (selection, reporting, channels) lives in ``streamcart_pytest``.
"""

__version__ = "0.1.0"
