"""Tests for foundry_core.gh helpers."""

from __future__ import annotations

from types import SimpleNamespace

from foundry_core.gh import get_score_from_labels


def _label(name: str) -> SimpleNamespace:
    return SimpleNamespace(name=name)


def _issue(labels: list[str]) -> SimpleNamespace:
    return SimpleNamespace(labels=[_label(n) for n in labels])


class TestGetScoreFromLabels:
    def test_ice_label(self) -> None:
        issue = _issue(["bug", "ice-7", "enhancement"])
        assert get_score_from_labels(issue) == 7

    def test_rice_label(self) -> None:
        issue = _issue(["rice-3"])
        assert get_score_from_labels(issue) == 3

    def test_no_matching_label(self) -> None:
        issue = _issue(["bug", "enhancement", "good-first-issue"])
        assert get_score_from_labels(issue) is None

    def test_empty_labels(self) -> None:
        issue = _issue([])
        assert get_score_from_labels(issue) is None

    def test_ice_10(self) -> None:
        issue = _issue(["ice-10"])
        assert get_score_from_labels(issue) == 10

    def test_ice_1(self) -> None:
        issue = _issue(["ice-1"])
        assert get_score_from_labels(issue) == 1

    def test_prefers_first_match(self) -> None:
        issue = _issue(["ice-3", "rice-9"])
        assert get_score_from_labels(issue) == 3

    def test_label_with_prefix_not_matched(self) -> None:
        issue = _issue(["xrice-5", "bug"])
        assert get_score_from_labels(issue) is None
