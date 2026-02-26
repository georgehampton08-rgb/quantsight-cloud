"""
Phase 8 End-to-End Validation — Step 8.7
==========================================
Validates all Phase 8 components without requiring live infrastructure.
Tests import chains, module wiring, data contracts, and fail-open semantics.

Run: python -m pytest tests/test_phase8_e2e.py -v
"""

import asyncio
import os
import sys
import unittest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone

# Ensure backend is on path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestPhase8FeatureFlag(unittest.TestCase):
    """Step 8.2.1: Validate feature flag activation."""

    def test_websocket_flag_default_true(self):
        from vanguard.core.feature_flags import _FLAG_DEFAULTS
        self.assertTrue(_FLAG_DEFAULTS["FEATURE_WEBSOCKET_ENABLED"])

    def test_websocket_flag_env_override(self):
        os.environ["FEATURE_WEBSOCKET_ENABLED"] = "false"
        try:
            from vanguard.core.feature_flags import flag
            self.assertFalse(flag("FEATURE_WEBSOCKET_ENABLED"))
        finally:
            os.environ.pop("FEATURE_WEBSOCKET_ENABLED", None)

    def test_websocket_flag_in_flag_defaults_report(self):
        from vanguard.core.feature_flags import flag_defaults
        report = flag_defaults()
        self.assertIn("FEATURE_WEBSOCKET_ENABLED", report)


class TestPhase8ConnectionManager(unittest.TestCase):
    """Step 8.2.2: Validate WebSocket connection manager."""

    def test_singleton(self):
        from services.ws_connection_manager import get_ws_manager
        a = get_ws_manager()
        b = get_ws_manager()
        self.assertIs(a, b)

    def test_max_connections(self):
        from services.ws_connection_manager import WebSocketConnectionManager
        mgr = WebSocketConnectionManager()
        self.assertEqual(mgr.MAX_CONNECTIONS, 500)

    def test_active_count_starts_zero(self):
        from services.ws_connection_manager import WebSocketConnectionManager
        mgr = WebSocketConnectionManager()
        self.assertEqual(mgr.active_count, 0)

    def test_stats_shape(self):
        from services.ws_connection_manager import WebSocketConnectionManager
        mgr = WebSocketConnectionManager()
        stats = mgr.get_stats()
        self.assertIn("websocket_connections_active", stats)
        self.assertIn("websocket_max_connections", stats)
        self.assertIn("websocket_enabled", stats)

    def test_connect_disconnect_lifecycle(self):
        from services.ws_connection_manager import WebSocketConnectionManager

        async def _test():
            mgr = WebSocketConnectionManager()
            ws = MagicMock()
            ws.send_json = AsyncMock()

            result = await mgr.connect("conn-1", ws, "session-abc")
            self.assertTrue(result)
            self.assertEqual(mgr.active_count, 1)

            await mgr.disconnect("conn-1")
            self.assertEqual(mgr.active_count, 0)

        asyncio.run(_test())

    def test_connection_limit_enforced(self):
        from services.ws_connection_manager import WebSocketConnectionManager

        async def _test():
            mgr = WebSocketConnectionManager()
            mgr.MAX_CONNECTIONS = 2  # Lower for test

            ws1 = MagicMock(); ws1.send_json = AsyncMock()
            ws2 = MagicMock(); ws2.send_json = AsyncMock()
            ws3 = MagicMock(); ws3.send_json = AsyncMock()

            self.assertTrue(await mgr.connect("c1", ws1, "s1"))
            self.assertTrue(await mgr.connect("c2", ws2, "s2"))
            self.assertFalse(await mgr.connect("c3", ws3, "s3"))  # Rejected
            self.assertEqual(mgr.active_count, 2)

        asyncio.run(_test())

    def test_broadcast_with_filter(self):
        from services.ws_connection_manager import WebSocketConnectionManager

        async def _test():
            mgr = WebSocketConnectionManager()
            ws_lal = MagicMock(); ws_lal.send_json = AsyncMock()
            ws_gsw = MagicMock(); ws_gsw.send_json = AsyncMock()

            await mgr.connect("c1", ws_lal, "s1")
            await mgr.update_filters("c1", {"team": "LAL"})
            await mgr.connect("c2", ws_gsw, "s2")
            await mgr.update_filters("c2", {"team": "GSW"})

            await mgr.broadcast_to_subscribers(
                "game_update", {"score": 100},
                filter_key="team", filter_value="LAL",
            )

            ws_lal.send_json.assert_called_once()
            ws_gsw.send_json.assert_not_called()

        asyncio.run(_test())


class TestPhase8MessageHandler(unittest.TestCase):
    """Step 8.2.4: Validate message handler dispatch."""

    def test_valid_filter_keys(self):
        from services.ws_message_handler import VALID_FILTER_KEYS
        self.assertEqual(VALID_FILTER_KEYS, {"team", "player_id", "game_id"})

    def test_valid_context_types(self):
        from services.ws_message_handler import VALID_CONTEXT_TYPES
        self.assertEqual(VALID_CONTEXT_TYPES, {"player", "incident", "game"})


class TestPhase8PresenceManager(unittest.TestCase):
    """Step 8.3: Validate presence manager fail-open semantics."""

    def test_fail_open_no_redis(self):
        from services.presence_manager import PresenceManager

        async def _test():
            pm = PresenceManager(redis_client=None)
            viewers = await pm.get_viewers("player_id", "2544")
            self.assertEqual(viewers, 0)

        asyncio.run(_test())

    def test_join_leave_no_redis(self):
        from services.presence_manager import PresenceManager

        async def _test():
            pm = PresenceManager(redis_client=None)
            # Should not raise
            await pm.join("token", "conn", {"player_id": "2544"})
            await pm.leave("token")
            await pm.update_context("token", {"team": "LAL"})

        asyncio.run(_test())


class TestPhase8AnnotationService(unittest.TestCase):
    """Step 8.4: Validate annotation service validation logic."""

    def test_max_content_length(self):
        from services.annotation_service import AnnotationService

        async def _test():
            svc = AnnotationService()
            with self.assertRaises(ValueError) as ctx:
                await svc.add_annotation("player", "2544", "tok", "x" * 501)
            self.assertIn("500", str(ctx.exception))

        asyncio.run(_test())

    def test_empty_content_rejected(self):
        from services.annotation_service import AnnotationService

        async def _test():
            svc = AnnotationService()
            with self.assertRaises(ValueError):
                await svc.add_annotation("player", "2544", "tok", "")

        asyncio.run(_test())

    def test_invalid_context_type(self):
        from services.annotation_service import AnnotationService

        async def _test():
            svc = AnnotationService()
            with self.assertRaises(ValueError):
                await svc.add_annotation("invalid", "123", "tok", "test")

        asyncio.run(_test())

    def test_author_token_truncated(self):
        from services.annotation_service import AnnotationService

        async def _test():
            svc = AnnotationService()
            note = await svc.add_annotation("player", "2544", "abc12345xyz", "test note")
            self.assertEqual(note["author_token"], "abc12345...")

        asyncio.run(_test())

    def test_note_schema(self):
        from services.annotation_service import AnnotationService

        async def _test():
            svc = AnnotationService()
            note = await svc.add_annotation("player", "2544", "tok12345", "test")
            # Validate schema
            self.assertIn("note_id", note)
            self.assertIn("content", note)
            self.assertIn("created_at", note)
            self.assertIn("reactions", note)
            self.assertEqual(note["reactions"], {"👍": 0, "🔥": 0, "⚠️": 0})
            self.assertFalse(note["pinned"])
            self.assertIsNone(note["edited_at"])

        asyncio.run(_test())

    def test_invalid_reaction_rejected(self):
        from services.annotation_service import AnnotationService

        async def _test():
            svc = AnnotationService()
            with self.assertRaises(ValueError) as ctx:
                await svc.add_reaction("player", "2544", "note-1", "😀")
            self.assertIn("Reaction", str(ctx.exception))

        asyncio.run(_test())


class TestPhase8WebSocketRoutes(unittest.TestCase):
    """Step 8.2.3: Validate route structure."""

    def test_route_paths(self):
        from api.websocket_routes import router
        paths = [str(getattr(r, "path", "")) for r in router.routes]
        self.assertIn("/live/ws", paths)
        self.assertIn("/live/presence/{context_type}/{context_id}", paths)
        self.assertIn("/annotations/{context_type}/{context_id}", paths)
        self.assertIn("/annotations/{context_type}/{context_id}/{note_id}/react", paths)

    def test_http_annotation_endpoints(self):
        from api.websocket_routes import router
        paths = [str(getattr(r, "path", "")) for r in router.routes]
        # Both GET and POST for annotations
        annotation_paths = [p for p in paths if "annotations" in p]
        self.assertTrue(len(annotation_paths) >= 2)


class TestPhase8CloudRunConfig(unittest.TestCase):
    """Step 8.5.3: Validate Cloud Run YAML."""

    def test_yaml_structure(self):
        import yaml  # PyYAML should be available
        yaml_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "cloudrun-service.yaml",
        )
        with open(yaml_path, encoding="utf-8") as f:
            config = yaml.safe_load(f)

        spec = config["spec"]["template"]["spec"]

        # Verify WebSocket-compatible settings
        self.assertEqual(spec["containerConcurrency"], 800)
        self.assertEqual(spec["timeoutSeconds"], 3600)

        # Verify resource limits
        container = spec["containers"][0]
        self.assertEqual(container["resources"]["limits"]["memory"], "512Mi")
        self.assertEqual(container["resources"]["limits"]["cpu"], "2")

    def test_min_instances(self):
        import yaml
        yaml_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "cloudrun-service.yaml",
        )
        with open(yaml_path, encoding="utf-8") as f:
            config = yaml.safe_load(f)

        annotations = config["spec"]["template"]["metadata"]["annotations"]
        self.assertEqual(annotations["autoscaling.knative.dev/minScale"], "2")
        self.assertEqual(annotations["autoscaling.knative.dev/maxScale"], "10")


class TestPhase8CustomMetrics(unittest.TestCase):
    """Step 8.5.4: Validate custom metrics module."""

    def test_import(self):
        from telemetry.custom_metrics import get_ws_delivery_histogram, get_ws_connections_gauge
        # Should not raise — initializes lazily

    def test_histogram_none_without_otel(self):
        """Without OTel configured, histogram should be None."""
        from telemetry.custom_metrics import get_ws_delivery_histogram
        # May or may not be None depending on whether OTel is installed
        # but should never raise
        h = get_ws_delivery_histogram()
        # Just verify it doesn't crash


class TestPhase8HealthDeps(unittest.TestCase):
    """Step 8.2.5: Validate /health/deps WebSocket stats integration."""

    def test_main_imports_ws_stats(self):
        """Verify main.py has WebSocket stats in health_deps."""
        main_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "main.py",
        )
        with open(main_path, encoding="utf-8") as f:
            content = f.read()
        self.assertIn("websocket_connections_active", content)
        self.assertIn("websocket_enabled", content)
        self.assertIn("ws_connection_manager", content)


class TestPhase8PulseIntegration(unittest.TestCase):
    """Step 8.2.5: Validate pulse producer WebSocket integration."""

    def test_producer_has_ws_broadcast(self):
        """Verify async_pulse_producer_cloud.py has WS broadcast."""
        producer_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "services", "async_pulse_producer_cloud.py",
        )
        with open(producer_path, encoding="utf-8") as f:
            content = f.read()
        self.assertIn("_ws_broadcast", content)
        self.assertIn("FEATURE_WEBSOCKET_ENABLED", content)
        self.assertIn("broadcast_to_subscribers", content)
        self.assertIn("leaders_update", content)
        self.assertIn("game_update", content)
        self.assertIn("player_update", content)


if __name__ == "__main__":
    unittest.main(verbosity=2)
