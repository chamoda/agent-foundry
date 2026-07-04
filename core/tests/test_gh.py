from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

from foundry_core.gh import get_score_from_labels


def _issue_with_labels(label_names: list[str]) -> MagicMock:
    labels = [MagicMock(name=n) for n in label_names]
    for name, label in zip(label_names, labels):
        label.name = name
    issue = MagicMock()
    issue.labels = labels
    return issue


class TestGetScoreFromLabels:
    def test_ice_label(self) -> None:
        issue = _issue_with_labels(["bug", "ice-7", "enhancement"])
        assert get_score_from_labels(issue) == 7

    def test_rice_label(self) -> None:
        issue = _issue_with_labels(["rice-3"])
        assert get_score_from_labels(issue) == 3

    def test_ice_10(self) -> None:
        issue = _issue_with_labels(["ice-10"])
        assert get_score_from_labels(issue) == 10

    def test_ice_1(self) -> None:
        issue = _issue_with_labels(["ice-1"])
        assert get_score_from_labels(issue) == 1

    def test_no_score_labels(self) -> None:
        issue = _issue_with_labels(["bug", "enhancement"])
        assert get_score_from_labels(issue) is None

    def test_empty_labels(self) -> None:
        issue = _issue_with_labels([])
        assert get_score_from_labels(issue) is None

    def test_ice_takes_precedence_over_rice(self) -> None:
        issue = _issue_with_labels(["rice-3", "ice-9"])
        assert get_score_from_labels(issue) == 3

    def test_ignores_similar_label_names(self) -> None:
        issue = _issue_with_labels(["nice-5", "price-2"])
        assert get_score_from_labels(issue) is None

    def test_ice_zero(self) -> None:
        issue = _issue_with_labels(["ice-0"])
        assert get_score_from_labels(issue) == 0

    def test_double_digit_score(self) -> None:
        issue = _issue_with_labels(["ice-10"])
        assert get_score_from_labels(issue) == 10
