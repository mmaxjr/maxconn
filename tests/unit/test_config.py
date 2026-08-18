from __future__ import annotations

import pytest

from maxconn.config import ALLOWED_KEYS, ConfigStore


def test_config_set_and_get_round_trips(tmp_path):
    store = ConfigStore(base_dir=tmp_path)

    store.set("timeout", "5")

    assert store.get("timeout") == "5"


def test_config_get_returns_none_for_an_unset_key(tmp_path):
    store = ConfigStore(base_dir=tmp_path)

    assert store.get("timeout") is None


def test_config_unset_removes_a_key(tmp_path):
    store = ConfigStore(base_dir=tmp_path)
    store.set("workers", "10")

    store.unset("workers")

    assert store.get("workers") is None


def test_config_unset_is_a_no_op_for_a_missing_key(tmp_path):
    store = ConfigStore(base_dir=tmp_path)

    store.unset("timeout")  # must not raise

    assert store.get("timeout") is None


def test_config_load_returns_all_set_values(tmp_path):
    store = ConfigStore(base_dir=tmp_path)
    store.set("timeout", "5")
    store.set("concurrency", "20")

    assert store.load() == {"timeout": "5", "concurrency": "20"}


def test_config_load_returns_empty_dict_for_a_missing_file(tmp_path):
    store = ConfigStore(base_dir=tmp_path)

    assert store.load() == {}


def test_config_load_returns_empty_dict_for_a_corrupted_file(tmp_path):
    # Regression: main() calls ConfigStore().load() unconditionally, before
    # its own try/except is even entered - a corrupted config.json (e.g. an
    # interrupted write, or manual editing) used to raise JSONDecodeError
    # there uncaught, bricking every single maxconn command with a raw
    # traceback until the user found and fixed/deleted the file by hand.
    store = ConfigStore(base_dir=tmp_path)
    store.config_path.parent.mkdir(parents=True, exist_ok=True)
    store.config_path.write_text("{not valid json", encoding="utf-8")

    assert store.load() == {}


def test_config_load_returns_empty_dict_when_the_file_is_not_a_json_object(tmp_path):
    store = ConfigStore(base_dir=tmp_path)
    store.config_path.parent.mkdir(parents=True, exist_ok=True)
    store.config_path.write_text("[1, 2, 3]", encoding="utf-8")

    assert store.load() == {}


def test_config_set_rejects_an_unknown_key(tmp_path):
    store = ConfigStore(base_dir=tmp_path)

    with pytest.raises(ValueError, match="unknown config key"):
        store.set("not-a-real-key", "value")


def test_allowed_keys_covers_the_documented_defaults():
    assert set(ALLOWED_KEYS) == {"timeout", "concurrency", "workers", "ports", "audit_log", "update_notify"}
