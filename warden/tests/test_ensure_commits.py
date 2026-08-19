from __future__ import annotations

from subprocess import CalledProcessError
from unittest.mock import MagicMock, call, patch

from warden.agent import _git_ok, ensure_commits


class TestGitOk:
    """Tests for the _git_ok boolean helper."""

    @patch("warden.agent.run")
    def test_returns_true_when_command_succeeds(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(stdout="")
        assert _git_ok(["cat-file", "-e", "abc123^{commit}"]) is True

    @patch("warden.agent.run")
    def test_returns_false_on_called_process_error(self, mock_run: MagicMock) -> None:
        mock_run.side_effect = CalledProcessError(128, ["git"])
        assert _git_ok(["cat-file", "-e", "abc123^{commit}"]) is False

    @patch("warden.agent.run")
    def test_returns_false_on_generic_exception(self, mock_run: MagicMock) -> None:
        mock_run.side_effect = OSError("git not found")
        assert _git_ok(["cat-file", "-e", "abc123^{commit}"]) is False


class TestEnsureCommits:
    """Tests for ensure_commits() fetching only when SHA is missing."""

    @patch("warden.agent._git")
    @patch("warden.agent._git_ok")
    def test_skips_fetch_when_sha_exists_locally(
        self, mock_ok: MagicMock, mock_git: MagicMock
    ) -> None:
        mock_ok.return_value = True
        ensure_commits("abc123")
        mock_ok.assert_called_once_with(
            ["cat-file", "-e", "abc123^{commit}"]
        )
        mock_git.assert_not_called()

    @patch("warden.agent._git")
    @patch("warden.agent._git_ok")
    def test_fetches_when_sha_is_missing_locally(
        self, mock_ok: MagicMock, mock_git: MagicMock
    ) -> None:
        mock_ok.return_value = False
        ensure_commits("abc123")
        mock_ok.assert_called_once_with(
            ["cat-file", "-e", "abc123^{commit}"]
        )
        mock_git.assert_called_once_with(
            ["fetch", "--no-tags", "--depth=200", "origin", "abc123"]
        )

    @patch("warden.agent._git")
    @patch("warden.agent._git_ok")
    def test_skips_empty_string(
        self, mock_ok: MagicMock, mock_git: MagicMock
    ) -> None:
        ensure_commits("")
        mock_ok.assert_not_called()
        mock_git.assert_not_called()

    @patch("warden.agent._git")
    @patch("warden.agent._git_ok")
    def test_mixed_shas_only_fetch_missing(
        self, mock_ok: MagicMock, mock_git: MagicMock
    ) -> None:
        mock_ok.side_effect = [True, False]
        ensure_commits("aaa", "bbb")
        assert mock_ok.call_count == 2
        mock_git.assert_called_once_with(
            ["fetch", "--no-tags", "--depth=200", "origin", "bbb"]
        )

    @patch("warden.agent._git")
    @patch("warden.agent._git_ok")
    def test_no_fetch_when_all_shas_present(
        self, mock_ok: MagicMock, mock_git: MagicMock
    ) -> None:
        mock_ok.return_value = True
        ensure_commits("aaa", "bbb", "ccc")
        assert mock_ok.call_count == 3
        mock_git.assert_not_called()
