"""Regression tests for #60328: --yolo must set HERMES_YOLO_MODE in
main() before _prepare_agent_startup() triggers tool imports.

The freeze mechanism in tools.approval (_YOLO_MODE_FROZEN) is correct
by design (PR #7994). The bug was that main() set the env var inside
cmd_chat(), which runs *after* _prepare_agent_startup() has already
imported tools.approval and frozen the constant to False.

These tests verify the ordering in main() itself: the env var must
already be set at the moment _prepare_agent_startup() is called.
If someone moves the assignment back into cmd_chat(), these tests
fail — catching the exact #60328 regression.
"""

import os
import sys

import pytest


def _run_main_and_capture_yolo_at_startup(monkeypatch, argv):
    """Run main() with *argv*, capturing HERMES_YOLO_MODE at the
    moment _prepare_agent_startup is called.

    Returns the captured env var value (or None if unset).
    """
    yolo_at_startup = {}

    def spy_prepare_startup(args):
        yolo_at_startup["value"] = os.environ.get("HERMES_YOLO_MODE")

    monkeypatch.setattr(
        "hermes_cli.main._prepare_agent_startup", spy_prepare_startup
    )
    # Stub cmd_chat so main() returns cleanly without entering chat.
    monkeypatch.setattr("hermes_cli.main.cmd_chat", lambda args: None)
    monkeypatch.delenv("HERMES_YOLO_MODE", raising=False)
    monkeypatch.setattr(sys, "argv", argv)

    from hermes_cli.main import main as cli_main

    cli_main()

    return yolo_at_startup.get("value")


def test_top_level_yolo_flag_sets_env_before_startup(monkeypatch):
    """hermes --yolo must set HERMES_YOLO_MODE before
    _prepare_agent_startup imports tools.approval."""
    result = _run_main_and_capture_yolo_at_startup(
        monkeypatch, ["hermes", "--yolo"]
    )
    assert result == "1", (
        "HERMES_YOLO_MODE was not '1' when _prepare_agent_startup was "
        "called from main() with --yolo. This is the #60328 regression: "
        "the env var is set too late (inside cmd_chat, after tool imports)."
    )


def test_top_level_oneshot_in_dir_pins_tools_before_startup(monkeypatch, tmp_path):
    """One-shot skips cmd_chat, so --in must be applied before tool imports."""
    import hermes_cli.main as main_mod

    target = tmp_path / "workspace"
    target.mkdir()
    stale = tmp_path / "launch"
    stale.mkdir()
    captured = {}
    start = os.getcwd()

    def spy_prepare_startup(args):
        captured["cwd"] = os.getcwd()
        captured["terminal_cwd"] = os.environ.get("TERMINAL_CWD")

    def stop_oneshot(*args, **kwargs):
        raise SystemExit(0)

    monkeypatch.setattr(main_mod, "_prepare_agent_startup", spy_prepare_startup)
    monkeypatch.setattr(main_mod, "_run_and_exit_oneshot", stop_oneshot)
    monkeypatch.setenv("TERMINAL_CWD", str(stale))
    monkeypatch.setattr(
        sys, "argv", ["hermes", "--in", str(target), "-z", "probe"]
    )

    try:
        with pytest.raises(SystemExit) as exc:
            main_mod.main()
        assert exc.value.code == 0
    finally:
        os.chdir(start)

    assert captured == {
        "cwd": str(target.resolve()),
        "terminal_cwd": str(target.resolve()),
    }


def test_termux_fast_oneshot_in_dir_pins_tools_before_startup(monkeypatch, tmp_path):
    """Termux fast one-shot must apply --in before startup and execution."""
    import hermes_cli.main as main_mod

    target = tmp_path / "workspace"
    target.mkdir()
    stale = tmp_path / "launch"
    stale.mkdir()
    captured = {}
    start = os.getcwd()

    def spy_prepare_startup(args):
        captured["startup"] = {
            "cwd": os.getcwd(),
            "terminal_cwd": os.environ.get("TERMINAL_CWD"),
        }

    def stop_oneshot(*args, **kwargs):
        captured["oneshot"] = {
            "cwd": os.getcwd(),
            "terminal_cwd": os.environ.get("TERMINAL_CWD"),
        }
        raise SystemExit(0)

    monkeypatch.setattr(main_mod, "_prepare_agent_startup", spy_prepare_startup)
    monkeypatch.setattr(main_mod, "_run_and_exit_oneshot", stop_oneshot)
    monkeypatch.setenv("TERMUX_VERSION", "0.118.3")
    monkeypatch.delenv("HERMES_TERMUX_DISABLE_FAST_CLI", raising=False)
    monkeypatch.setenv("TERMINAL_CWD", str(stale))
    monkeypatch.setattr(
        sys, "argv", ["hermes", "--in", str(target), "-z", "probe"]
    )

    try:
        with pytest.raises(SystemExit) as exc:
            main_mod.main()
        assert exc.value.code == 0
    finally:
        os.chdir(start)

    expected = {
        "cwd": str(target.resolve()),
        "terminal_cwd": str(target.resolve()),
    }
    assert captured == {"startup": expected, "oneshot": expected}


