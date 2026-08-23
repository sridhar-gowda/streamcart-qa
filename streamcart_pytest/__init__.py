"""The StreamCart execution platform — a pytest plugin.

Everything a run needs beyond the tests themselves, inside pytest: selection
(``--platform``, ``--env``, ``--target``, suites, TMS plans), run identity,
failure classification, evidence capture, result channels (TMS, artifact stores,
dashboards) and flakiness analytics.

Registered automatically via the ``pytest11`` entry point on ``pip install -e .``.
"""

__all__ = ["plugin"]
