import pytest

from piper_jobs.cli import main


def test_help_lists_commands(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["--help"])
    assert exc.value.code == 0
    out = capsys.readouterr().out
    for cmd in ("ui", "sync", "doctor", "seed", "stats", "reset"):
        assert cmd in out


def test_legacy_data_folder_moves_once(tmp_path):
    from piper_jobs.config import migrate_legacy_data_dir

    old, new = tmp_path / ".jobtracker", tmp_path / ".piper"
    old.mkdir()
    (old / "jobs.db").write_text("data")
    assert migrate_legacy_data_dir(old, new) is True
    assert (new / "jobs.db").read_text() == "data" and not old.exists()
    old.mkdir()  # a stray old folder never overwrites the new one
    assert migrate_legacy_data_dir(old, new) is False and (new / "jobs.db").exists()
