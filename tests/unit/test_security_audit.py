"""Tests for security audit logging utilities."""

from __future__ import annotations

from psim_mcp.utils.logging import hash_input, SecurityAuditLogger


# ------------------------------------------------------------------
# hash_input
# ------------------------------------------------------------------


class TestHashInput:
    """Ensure hash_input produces consistent, fixed-length hashes."""

    def test_consistent_hash(self):
        assert hash_input("test_value") == hash_input("test_value")

    def test_different_inputs_different_hashes(self):
        assert hash_input("input_a") != hash_input("input_b")

    def test_output_length_is_16(self):
        result = hash_input("anything")
        assert len(result) == 16

    def test_output_is_hex(self):
        result = hash_input("some value")
        # All chars should be valid hex digits
        assert all(c in "0123456789abcdef" for c in result)

    def test_empty_string(self):
        result = hash_input("")
        assert len(result) == 16


# ------------------------------------------------------------------
# SecurityAuditLogger
# ------------------------------------------------------------------


class TestSecurityAuditLogger:
    """Ensure SecurityAuditLogger can be instantiated and called without errors."""

    def test_instantiation(self):
        logger = SecurityAuditLogger()
        assert logger is not None

    def test_custom_logger_name(self):
        logger = SecurityAuditLogger("test.security")
        assert logger is not None

    def test_log_tool_call_no_exception(self):
        logger = SecurityAuditLogger()
        # Should not raise
        logger.log_tool_call("test_tool", {"key": "value"}, 100.0, True)

    def test_log_tool_call_failure(self):
        logger = SecurityAuditLogger()
        logger.log_tool_call("test_tool", {}, 50.0, False)

    def test_log_path_blocked_no_exception(self):
        logger = SecurityAuditLogger()
        logger.log_path_blocked("/secret/path", "not_allowed")

    def test_log_invalid_input_no_exception(self):
        logger = SecurityAuditLogger()
        logger.log_invalid_input("some_tool", "field_x", "bad format")

    def test_log_subprocess_event_no_exception(self):
        logger = SecurityAuditLogger()
        logger.log_subprocess_event("run_sim", 200.0, True)

    def test_log_subprocess_event_with_error(self):
        logger = SecurityAuditLogger()
        logger.log_subprocess_event("run_sim", 200.0, False, error="timeout")

    def test_log_rate_limit_no_exception(self):
        logger = SecurityAuditLogger()
        logger.log_rate_limit("fast_tool", "too many calls")
