import pytest

from jobtracker.cli import main


def test_help_lists_commands(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["--help"])
    assert exc.value.code == 0
    out = capsys.readouterr().out
    for cmd in ("ui", "sync", "doctor", "seed", "stats", "reset"):
        assert cmd in out
