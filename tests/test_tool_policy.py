import unittest

from src.utils.tool_policy import check_tool_call, classify_action, operation_id, sanitize_params


POLICY = {
    "default_risk": "write",
    "confirmation": {
        "require_for_risks": ["write", "delete", "dangerous"],
        "allowlisted_writes": [],
    },
    "tools": {
        "timeline_markers": {
            "read_actions": ["get_all"],
            "write_actions": ["add"],
            "delete_actions": ["delete_at_frame"],
        }
    },
}


class ToolPolicyTests(unittest.TestCase):
    def test_read_action_is_allowed(self):
        decision = check_tool_call(POLICY, "timeline_markers", "get_all", {})

        self.assertTrue(decision.allowed)
        self.assertEqual(decision.risk, "read")

    def test_unknown_action_defaults_to_write(self):
        self.assertEqual(classify_action(POLICY, "new_tool", "surprise"), "write")

    def test_write_without_confirmation_returns_preview(self):
        decision = check_tool_call(POLICY, "timeline_markers", "add", {"frame": 12})

        self.assertFalse(decision.allowed)
        self.assertEqual(decision.response["requires_confirmation"], True)
        self.assertEqual(decision.response["preview"]["params"], {"frame": 12})

    def test_write_requires_matching_operation_id(self):
        params = {"frame": 12}
        op_id = operation_id("timeline_markers", "add", params)

        denied = check_tool_call(
            POLICY,
            "timeline_markers",
            "add",
            {"frame": 12, "confirm": True, "operation_id": "wrong"},
        )
        allowed = check_tool_call(
            POLICY,
            "timeline_markers",
            "add",
            {"frame": 12, "confirm": True, "operation_id": op_id},
        )

        self.assertFalse(denied.allowed)
        self.assertTrue(allowed.allowed)

    def test_confirmation_fields_do_not_change_operation_id(self):
        base = operation_id("timeline_markers", "add", {"frame": 12})
        confirmed = operation_id(
            "timeline_markers",
            "add",
            {"frame": 12, "confirm": True, "operation_id": base, "reason": "approved"},
        )

        self.assertEqual(base, confirmed)

    def test_sanitize_params_removes_nested_confirmation_keys(self):
        self.assertEqual(
            sanitize_params({"a": {"confirm": True, "value": 1}, "operation_id": "abc"}),
            {"a": {"value": 1}},
        )


if __name__ == "__main__":
    unittest.main()
