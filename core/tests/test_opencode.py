from unittest.mock import patch

from foundry_core.opencode import _to_opencode_server


@patch("foundry_core.opencode.log")
class TestToOpencodeServerEnabled:
    """Verify that the ``enabled`` flag is propagated from the source spec."""

    def test_remote_enabled_false_propagated(self, _mock_log):
        spec = {"url": "http://example.com/mcp", "enabled": False}
        result = _to_opencode_server("test", spec)
        assert result is not None
        assert result["enabled"] is False

    def test_remote_enabled_true_propagated(self, _mock_log):
        spec = {"url": "http://example.com/mcp", "enabled": True}
        result = _to_opencode_server("test", spec)
        assert result is not None
        assert result["enabled"] is True

    def test_remote_enabled_omitted_defaults_true(self, _mock_log):
        spec = {"url": "http://example.com/mcp"}
        result = _to_opencode_server("test", spec)
        assert result is not None
        assert result["enabled"] is True

    def test_local_enabled_false_propagated(self, _mock_log):
        spec = {"command": "my-server", "enabled": False}
        result = _to_opencode_server("test", spec)
        assert result is not None
        assert result["enabled"] is False

    def test_local_enabled_true_propagated(self, _mock_log):
        spec = {"command": "my-server", "enabled": True}
        result = _to_opencode_server("test", spec)
        assert result is not None
        assert result["enabled"] is True

    def test_local_enabled_omitted_defaults_true(self, _mock_log):
        spec = {"command": "my-server"}
        result = _to_opencode_server("test", spec)
        assert result is not None
        assert result["enabled"] is True


@patch("foundry_core.opencode.log")
class TestToOpencodeServerBasic:
    """Basic translation behaviour (non-``enabled`` aspects)."""

    def test_returns_none_for_non_dict(self, _mock_log):
        assert _to_opencode_server("test", "not a dict") is None

    def test_remote_server_has_type_and_url(self, _mock_log):
        result = _to_opencode_server("test", {"url": "http://x"})
        assert result == {"type": "remote", "url": "http://x", "enabled": True}

    def test_remote_server_with_headers(self, _mock_log):
        spec = {"url": "http://x", "headers": {"Authorization": "Bearer t"}}
        result = _to_opencode_server("test", spec)
        assert result is not None
        assert result["headers"] == {"Authorization": "Bearer t"}

    def test_local_server_command_string(self, _mock_log):
        spec = {"command": "node", "args": ["server.js"]}
        result = _to_opencode_server("test", spec)
        assert result is not None
        assert result["type"] == "local"
        assert result["command"] == ["node", "server.js"]

    def test_local_server_command_list(self, _mock_log):
        spec = {"command": ["python3", "-m", "server"]}
        result = _to_opencode_server("test", spec)
        assert result is not None
        assert result["command"] == ["python3", "-m", "server"]

    def test_local_server_with_env(self, _mock_log):
        spec = {"command": "srv", "env": {"FOO": "bar"}}
        result = _to_opencode_server("test", spec)
        assert result is not None
        assert result["environment"] == {"FOO": "bar"}

    def test_returns_none_when_no_command_or_url(self, _mock_log):
        assert _to_opencode_server("test", {"foo": "bar"}) is None
