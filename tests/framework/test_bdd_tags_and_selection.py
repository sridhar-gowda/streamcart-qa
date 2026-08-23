"""Gherkin tag mapping and collection-time selection (platform, suite, capability, TMS ids)."""

from __future__ import annotations

from pathlib import Path

import pytest

from streamcart_pytest.bdd import marker_for_tag

from .conftest import plugin_args

REPO_CONFIG = Path(__file__).resolve().parents[2] / "config"


@pytest.mark.parametrize(
    ("tag", "name", "args"),
    [
        ("smoke", "suite", ("smoke",)),
        ("e2e", "suite", ("e2e",)),
        ("roku", "platform", ("roku",)),
        ("web", "platform", ("web",)),
        ("critical", "critical", ()),
        ("quarantine", "quarantine", ()),
        ("requires:swipe", "requires", ("swipe",)),
        ("requires:dpad,focus_navigation", "requires", ("dpad", "focus_navigation")),
        ("known_issue:SC-123", "known_issue", ("SC-123",)),
        ("TC-LOGIN-001", "tms", ("TC-LOGIN-001",)),
        ("XRAY-1042", "tms", ("XRAY-1042",)),
        ("CB-55", "tms", ("CB-55",)),
        ("login", "feature", ("login",)),
        ("platform-divergence", "feature", ("platform-divergence",)),
    ],
)
def test_tags_become_markers(tag: str, name: str, args: tuple[str, ...]) -> None:
    marker = marker_for_tag(tag)
    assert marker.name == name
    assert marker.args == args


@pytest.fixture(autouse=True)
def _use_repo_config(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("STREAMCART_CONFIG_DIR", str(REPO_CONFIG))


SELECTION_TESTS = """
import pytest

@pytest.mark.platform("roku", "firetv")
def test_tv_only(): pass

@pytest.mark.suite("smoke")
@pytest.mark.tms("TC-1")
def test_smoke(): pass

@pytest.mark.tms("TC-2")
def test_regression_by_default(): pass

@pytest.mark.requires("swipe")
def test_needs_swipe(): pass

@pytest.mark.requires("keyboard")
def test_needs_keyboard(): pass
"""


def test_platform_mismatch_deselects_and_missing_capability_skips(pytester: pytest.Pytester) -> None:
    pytester.makepyfile(SELECTION_TESTS)
    result = pytester.runpytest("--platform", "web", "-rs", *plugin_args())
    result.assert_outcomes(passed=3, skipped=1, deselected=1)
    result.stdout.fnmatch_lines(["*platform 'web' lacks capability: swipe*"])
    result.stdout.fnmatch_lines(["*1 scenario(s) deselected: tagged for other platforms*"])


def test_on_a_tv_platform_the_selection_flips(pytester: pytest.Pytester) -> None:
    pytester.makepyfile(SELECTION_TESTS)
    result = pytester.runpytest("--platform", "roku", "-rs", *plugin_args())
    # tv_only runs, swipe AND keyboard are skipped (no touch, no physical keyboard on a remote)
    result.assert_outcomes(passed=3, skipped=2)
    result.stdout.fnmatch_lines(["*platform 'roku' lacks capability: keyboard*"])


def test_suite_and_tms_selection(pytester: pytest.Pytester) -> None:
    pytester.makepyfile(SELECTION_TESTS)
    smoke = pytester.runpytest("--platform", "web", "--suite", "smoke", *plugin_args())
    smoke.assert_outcomes(passed=1, deselected=4)
    regression = pytester.runpytest("--platform", "web", "--suite", "regression", *plugin_args())
    regression.assert_outcomes(passed=3, skipped=1, deselected=1)  # everything untagged is regression
    by_id = pytester.runpytest("--platform", "web", "--tms-ids", "TC-2", *plugin_args())
    by_id.assert_outcomes(passed=1, deselected=4)


def test_framework_suite_is_never_part_of_the_product_regression(pytester: pytest.Pytester) -> None:
    pytester.makepyfile(
        """
        import pytest
        @pytest.mark.suite("framework")
        def test_tooling(): pass
        def test_product_scenario(): pass
        """
    )
    result = pytester.runpytest("--suite", "regression", *plugin_args())
    result.assert_outcomes(passed=1, deselected=1)


def test_unknown_capability_is_a_usage_error(pytester: pytest.Pytester) -> None:
    pytester.makepyfile(
        """
        import pytest
        @pytest.mark.requires("telepathy")
        def test_x(): pass
        """
    )
    result = pytester.runpytest("--platform", "web", *plugin_args())
    assert result.ret == pytest.ExitCode.USAGE_ERROR
    result.stderr.fnmatch_lines(["*unknown capability 'telepathy' in @requires*"])
