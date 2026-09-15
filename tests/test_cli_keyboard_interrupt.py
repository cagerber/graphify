"""CLI must exit 130 on Ctrl+C without a traceback."""

from __future__ import annotations

import pytest


def test_main_keyboard_interrupt_exits_130(monkeypatch: pytest.MonkeyPatch) -> None:
    import graphify.__main__ as cli

    def _interrupt() -> None:
        raise KeyboardInterrupt

    monkeypatch.setattr(cli, "_run_cli", _interrupt)

    with pytest.raises(SystemExit) as exc:
        cli.main()
    assert exc.value.code == 130
