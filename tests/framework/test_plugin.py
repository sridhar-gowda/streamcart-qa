from __future__ import annotations

from pathlib import Path

import pytest

from .conftest import plugin_args

REPO_CONFIG = Path(__file__).resolve().parents[2] / "config"


@pytest.fixture(autouse=True)
def _use_repo_config(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("STREAMCART_CONFIG_DIR", str(REPO_CONFIG))
    monkeypatch.delenv("STREAMCART_RUN_ID", raising=False)


def test_header_shows_platform_and_layers(pytester: pytest.Pytester) -> None:
    pytester.makepyfile("def test_ok(): pass")
    result = pytester.runpytest("--platform", "roku", "--env", "staging", "--run-id", "r-1", *plugin_args())
    result.assert_outcomes(passed=1)
    result.stdout.re_match_lines([r"streamcart: platform=roku \(tv\) \| env=staging \| target=roku-lab .* run_id=r-1"])
    result.stdout.fnmatch_lines(["*base.yaml -> platform/roku.yaml -> target/roku-lab.yaml -> env/staging.yaml*"])


def test_settings_fixture_and_cli_overrides(pytester: pytest.Pytester) -> None:
    pytester.makepyfile(
        """
        def test_settings(settings, run_id):
            assert settings.platform.name == "web"
            assert settings.app.base_url == "http://localhost:3000"
            assert settings.web.headless is False
            assert settings.run_id == run_id and len(run_id) == len("20260822_143021_f47ac10b")
        """
    )
    result = pytester.runpytest("--base-url", "http://localhost:3000", "--headed", *plugin_args())
    result.assert_outcomes(passed=1)


def test_bad_configuration_fails_fast_with_guidance(pytester: pytest.Pytester) -> None:
    pytester.makepyfile("def test_never_runs(): pass")
    result = pytester.runpytest("--target", "nope", *plugin_args())
    assert result.ret == pytest.ExitCode.USAGE_ERROR
    result.stderr.fnmatch_lines(["*streamcart configuration error: No target configuration named 'nope'*"])


def test_markers_are_registered_strictly(pytester: pytest.Pytester) -> None:
    pytester.makepyfile(
        """
        import pytest
        @pytest.mark.platform("web")
        @pytest.mark.tms("XRAY-1")
        def test_marked(): pass
        """
    )
    result = pytester.runpytest("--strict-markers", *plugin_args())
    result.assert_outcomes(passed=1)
