"""Focused checks for the supported disposable Big Orbit bootstrap helper."""

from __future__ import annotations

from subprocess import CompletedProcess

import pytest

from infra.scripts import prepare_big_orbit_smoke as smoke


def test_issue_pin_captures_exact_cli_value_without_shell(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The PIN is parsed from captured output and never interpolated into a shell."""

    captured: dict[str, object] = {}

    def run(command: list[str], **kwargs: object) -> CompletedProcess[str]:
        captured["command"] = command
        captured["kwargs"] = kwargs
        return CompletedProcess(
            command,
            0,
            stdout="Big Orbit bootstrap PIN: 12345678\nThis PIN expires in 10 minutes.\n",
            stderr="",
        )

    monkeypatch.setattr(smoke.subprocess, "run", run)

    assert smoke.issue_pin("owner@example.com") == "12345678"
    command = captured["command"]
    assert isinstance(command, list)
    assert command[-2:] == ["bootstrap-admin", "owner@example.com"]
    assert captured["kwargs"] == {
        "capture_output": True,
        "text": True,
        "check": False,
    }


def test_issue_pin_failure_never_echoes_captured_secret(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """CLI failures do not put captured stdout or stderr into an exception."""

    def run(command: list[str], **_kwargs: object) -> CompletedProcess[str]:
        return CompletedProcess(command, 1, stdout="87654321", stderr="private detail")

    monkeypatch.setattr(smoke.subprocess, "run", run)

    with pytest.raises(RuntimeError) as failure:
        smoke.issue_pin("owner@example.com")
    assert "87654321" not in str(failure.value)
    assert "private detail" not in str(failure.value)


@pytest.mark.parametrize("stdout", ["", "Big Orbit bootstrap PIN: 1234567\n"])
def test_issue_pin_rejects_missing_or_malformed_output(
    monkeypatch: pytest.MonkeyPatch, stdout: str
) -> None:
    """Only the CLI's exact eight-digit response is accepted."""

    def run(command: list[str], **_kwargs: object) -> CompletedProcess[str]:
        return CompletedProcess(command, 0, stdout=stdout, stderr="")

    monkeypatch.setattr(smoke.subprocess, "run", run)

    with pytest.raises(RuntimeError, match="invalid response"):
        smoke.issue_pin("owner@example.com")


def test_required_response_helpers_fail_without_serializing_payload() -> None:
    """Secret-bearing response objects are never copied into diagnostics."""

    payload = {"secret": "must-not-appear"}
    with pytest.raises(RuntimeError) as missing_string:
        smoke.required_string(payload, "access_token")
    with pytest.raises(RuntimeError) as missing_object:
        smoke.required_object(payload, "challenge")
    assert "must-not-appear" not in str(missing_string.value)
    assert "must-not-appear" not in str(missing_object.value)
