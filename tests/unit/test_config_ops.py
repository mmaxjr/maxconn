from __future__ import annotations

from maxconn.cli._config_ops import DEFAULT_BACKUP_COMMANDS, _safe_name


def test_default_backup_commands_cover_common_vendors():
    assert DEFAULT_BACKUP_COMMANDS["cisco"] == "show running-config"
    assert DEFAULT_BACKUP_COMMANDS["huawei"] == "display current-configuration"
    assert DEFAULT_BACKUP_COMMANDS["mikrotik"] == "export"


def test_safe_name_replaces_unsafe_characters():
    assert _safe_name("192.0.2.10") == "192.0.2.10"
    assert _safe_name("olt-01") == "olt-01"
    assert _safe_name("a b/c") == "a_b_c"
