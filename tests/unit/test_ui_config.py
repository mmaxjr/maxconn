from __future__ import annotations

from maxconn.hosts import DEFAULT_BASE_DIR
from maxconn.ui.config import config_path, load_theme, save_theme


def test_config_path_lives_under_the_shared_maxconn_base_dir():
    # hosts.py and history.py both store their data under ~/.maxconn
    # (DEFAULT_BASE_DIR); the UI theme config previously used a separate
    # platform-specific convention (%APPDATA%/XDG_CONFIG_HOME) instead of
    # sharing it, which was confusing for anyone looking for maxconn's data.
    path = config_path()
    assert path.parent == DEFAULT_BASE_DIR
    assert path.name == "config.json"


def test_load_theme_returns_none_when_nothing_saved_yet(tmp_path):
    assert load_theme(base_dir=tmp_path) is None


def test_save_then_load_theme_round_trips(tmp_path):
    save_theme("matrix", base_dir=tmp_path)
    assert load_theme(base_dir=tmp_path) == "matrix"


def test_save_theme_writes_under_the_given_base_dir(tmp_path):
    save_theme("solid", base_dir=tmp_path)
    assert (tmp_path / "config.json").exists()


def test_load_theme_returns_none_for_corrupted_config_file(tmp_path):
    (tmp_path / "config.json").write_text("not valid json", encoding="utf-8")
    assert load_theme(base_dir=tmp_path) is None
