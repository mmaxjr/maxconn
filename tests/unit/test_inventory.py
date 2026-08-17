from __future__ import annotations

from maxconn.cli._inventory import reconcile


class _FakeDiscoverHost:
    def __init__(self, host, reachable):
        self.host = host
        self._reachable = reachable

    @property
    def reachable(self):
        return self._reachable


def test_reconcile_matches_documented_and_reachable_hosts():
    result = reconcile(planned_hosts=["10.0.0.1", "10.0.0.2"], discovered=[_FakeDiscoverHost("10.0.0.1", True)])

    assert result.matched == {"10.0.0.1"}
    assert result.missing == {"10.0.0.2"}
    assert result.undocumented == set()


def test_reconcile_finds_undocumented_reachable_hosts():
    result = reconcile(
        planned_hosts=["10.0.0.1"],
        discovered=[_FakeDiscoverHost("10.0.0.1", True), _FakeDiscoverHost("10.0.0.99", True)],
    )

    assert result.undocumented == {"10.0.0.99"}


def test_reconcile_ignores_unreachable_discovered_hosts():
    result = reconcile(planned_hosts=[], discovered=[_FakeDiscoverHost("10.0.0.5", False)])

    assert result.undocumented == set()


def test_reconcile_is_clean_when_everything_matches():
    result = reconcile(planned_hosts=["10.0.0.1"], discovered=[_FakeDiscoverHost("10.0.0.1", True)])

    assert result.is_clean is True


def test_reconcile_is_not_clean_with_drift():
    result = reconcile(planned_hosts=["10.0.0.1"], discovered=[])

    assert result.is_clean is False
