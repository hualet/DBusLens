import unittest

from dbuslens.name_timeline import NameTimelineResolver


class NameTimelineResolverTests(unittest.TestCase):
    def test_resolve_unique_name_to_well_known_alias_at_event_time(self) -> None:
        resolver = NameTimelineResolver.from_payload(
            {
                "captured_at": "2026-04-16T10:20:30+08:00",
                "bus": "session",
                "names": [
                    {
                        "name": "org.example.Service",
                        "owner": ":1.42",
                        "pid": 4242,
                        "uid": 1000,
                        "cmdline": ["/bin/service"],
                        "error": None,
                    }
                ],
            },
            {
                "bus": "session",
                "started_at": "2026-04-16T10:20:30+08:00",
                "ended_at": "2026-04-16T10:20:40+08:00",
                "initial_snapshot": {
                    "captured_at": "2026-04-16T10:20:30+08:00",
                    "bus": "session",
                    "names": [
                        {
                            "name": "org.example.Service",
                            "owner": ":1.42",
                            "pid": 4242,
                            "uid": 1000,
                            "cmdline": ["/bin/service"],
                            "error": None,
                        }
                    ],
                },
                "events": [],
                "final_snapshot": {
                    "captured_at": "2026-04-16T10:20:40+08:00",
                    "bus": "session",
                    "names": [],
                },
                "error": None,
            },
        )

        resolved = resolver.resolve_name(":1.42", timestamp=1713243600.5)

        self.assertEqual(resolved.display_name, "org.example.Service")
        self.assertEqual(resolved.pid, 4242)

    def test_resolve_unique_name_prefers_well_known_alias_then_lexical_order(self) -> None:
        resolver = NameTimelineResolver.from_payload(
            {
                "captured_at": "2026-04-16T10:20:30+08:00",
                "bus": "session",
                "names": [
                    {
                        "name": "org.example.Alpha",
                        "owner": ":1.42",
                        "pid": 4242,
                        "uid": 1000,
                        "cmdline": ["/bin/service"],
                        "error": None,
                    },
                    {
                        "name": ":1.42",
                        "owner": ":1.42",
                        "pid": 4242,
                        "uid": 1000,
                        "cmdline": ["/bin/service"],
                        "error": None,
                    },
                    {
                        "name": "org.example.Zebra",
                        "owner": ":1.42",
                        "pid": 4242,
                        "uid": 1000,
                        "cmdline": ["/bin/service"],
                        "error": None,
                    },
                ],
            },
            {
                "bus": "session",
                "started_at": "2026-04-16T10:20:30+08:00",
                "ended_at": "2026-04-16T10:20:40+08:00",
                "initial_snapshot": {
                    "captured_at": "2026-04-16T10:20:30+08:00",
                    "bus": "session",
                    "names": [
                        {
                            "name": "org.example.Alpha",
                            "owner": ":1.42",
                            "pid": 4242,
                            "uid": 1000,
                            "cmdline": ["/bin/service"],
                            "error": None,
                        },
                        {
                            "name": ":1.42",
                            "owner": ":1.42",
                            "pid": 4242,
                            "uid": 1000,
                            "cmdline": ["/bin/service"],
                            "error": None,
                        },
                        {
                            "name": "org.example.Zebra",
                            "owner": ":1.42",
                            "pid": 4242,
                            "uid": 1000,
                            "cmdline": ["/bin/service"],
                            "error": None,
                        },
                    ],
                },
                "events": [],
                "final_snapshot": {
                    "captured_at": "2026-04-16T10:20:40+08:00",
                    "bus": "session",
                    "names": [],
                },
                "error": None,
            },
        )

        resolved = resolver.resolve_name(":1.42", timestamp=1713243600.5)

        self.assertEqual(resolved.display_name, "org.example.Alpha")
        self.assertEqual(resolved.owner, ":1.42")
        self.assertEqual(resolved.pid, 4242)

    def test_resolve_name_uses_timeline_for_short_lived_client(self) -> None:
        resolver = NameTimelineResolver.from_payload(
            {"captured_at": "2026-04-16T10:20:30+08:00", "bus": "session", "names": []},
            {
                "bus": "session",
                "started_at": "2026-04-16T10:20:30+08:00",
                "ended_at": "2026-04-16T10:20:40+08:00",
                "initial_snapshot": {
                    "captured_at": "2026-04-16T10:20:30+08:00",
                    "bus": "session",
                    "names": [
                        {
                            "name": "org.example.Service",
                            "owner": ":1.42",
                            "pid": 4242,
                            "uid": 1000,
                            "cmdline": ["/bin/service-old"],
                            "error": None,
                        }
                    ],
                },
                "events": [
                    {
                        "timestamp": 1713243604.0,
                        "name": "org.example.ShortLived",
                        "old_owner": "",
                        "new_owner": ":1.99",
                    }
                ],
                "final_snapshot": {
                    "captured_at": "2026-04-16T10:20:40+08:00",
                    "bus": "session",
                    "names": [
                        {
                            "name": "org.example.ShortLived",
                            "owner": ":1.99",
                            "pid": 9900,
                            "uid": 1000,
                            "cmdline": ["/bin/short-lived"],
                            "error": None,
                        }
                    ],
                },
                "error": None,
            },
        )

        resolved = resolver.resolve_name(":1.99", timestamp=1713243605.0)

        self.assertEqual(resolved.display_name, "org.example.ShortLived")
        self.assertEqual(resolved.owner, ":1.99")
        self.assertEqual(resolved.pid, 9900)

    def test_resolve_name_keeps_raw_value_when_no_mapping_exists(self) -> None:
        resolver = NameTimelineResolver.from_payload(
            {"captured_at": "2026-04-16T10:20:30+08:00", "bus": "session", "names": []},
            None,
        )

        resolved = resolver.resolve_name(":1.404", timestamp=1713243600.5)

        self.assertEqual(resolved.display_name, ":1.404")
        self.assertEqual(resolved.raw_name, ":1.404")
        self.assertIsNone(resolved.pid)

    def test_resolve_name_handles_owner_disappearance(self) -> None:
        resolver = NameTimelineResolver.from_payload(
            {"captured_at": "2026-04-16T10:20:30+08:00", "bus": "session", "names": []},
            {
                "bus": "session",
                "started_at": "2026-04-16T10:20:30+08:00",
                "ended_at": "2026-04-16T10:20:40+08:00",
                "initial_snapshot": {
                    "captured_at": "2026-04-16T10:20:30+08:00",
                    "bus": "session",
                    "names": [
                        {
                            "name": "org.example.Service",
                            "owner": ":1.42",
                            "pid": 4242,
                            "uid": 1000,
                            "cmdline": ["/bin/service"],
                            "error": None,
                        }
                    ],
                },
                "events": [
                    {
                        "timestamp": 1713243602.0,
                        "name": "org.example.Service",
                        "old_owner": ":1.42",
                        "new_owner": "",
                    }
                ],
                "final_snapshot": {
                    "captured_at": "2026-04-16T10:20:40+08:00",
                    "bus": "session",
                    "names": [],
                },
                "error": None,
            },
        )

        resolved = resolver.resolve_name(":1.42", timestamp=1713243603.0)

        self.assertEqual(resolved.display_name, ":1.42")
        self.assertIsNone(resolved.pid)

    def test_resolve_name_prefers_new_owner_metadata_after_handoff(self) -> None:
        resolver = NameTimelineResolver.from_payload(
            {
                "captured_at": "2026-04-16T10:20:30+08:00",
                "bus": "session",
                "names": [
                    {
                        "name": "org.example.Service",
                        "owner": ":1.42",
                        "pid": 4242,
                        "uid": 1000,
                        "cmdline": ["/bin/service-old"],
                        "error": None,
                    }
                ],
            },
            {
                "bus": "session",
                "started_at": "2026-04-16T10:20:30+08:00",
                "ended_at": "2026-04-16T10:20:40+08:00",
                "initial_snapshot": {
                    "captured_at": "2026-04-16T10:20:30+08:00",
                    "bus": "session",
                    "names": [],
                },
                "events": [
                    {
                        "timestamp": 1713243602.0,
                        "name": "org.example.Service",
                        "old_owner": ":1.42",
                        "new_owner": ":1.77",
                    }
                ],
                "final_snapshot": {
                    "captured_at": "2026-04-16T10:20:40+08:00",
                    "bus": "session",
                    "names": [
                        {
                            "name": "org.example.Service",
                            "owner": ":1.77",
                            "pid": 7777,
                            "uid": 1000,
                            "cmdline": ["/bin/service-new"],
                            "error": None,
                        }
                    ],
                },
                "error": None,
            },
        )

        resolved = resolver.resolve_name(":1.77", timestamp=1713243603.0)

        self.assertEqual(resolved.display_name, "org.example.Service")
        self.assertEqual(resolved.owner, ":1.77")
        self.assertEqual(resolved.pid, 7777)
        self.assertEqual(resolved.cmdline, ["/bin/service-new"])

    def test_resolve_name_keeps_explicit_empty_timeline_snapshots_empty(self) -> None:
        resolver = NameTimelineResolver.from_payload(
            {
                "captured_at": "2026-04-16T10:20:30+08:00",
                "bus": "session",
                "names": [
                    {
                        "name": "org.example.Service",
                        "owner": ":1.42",
                        "pid": 4242,
                        "uid": 1000,
                        "cmdline": ["/bin/service"],
                        "error": None,
                    }
                ],
            },
            {
                "bus": "session",
                "started_at": "2026-04-16T10:20:30+08:00",
                "ended_at": "2026-04-16T10:20:40+08:00",
                "initial_snapshot": {},
                "events": [],
                "final_snapshot": {},
                "error": None,
            },
        )

        resolved = resolver.resolve_name(":1.42", timestamp=1713243600.5)

        self.assertEqual(resolved.display_name, ":1.42")
        self.assertIsNone(resolved.pid)

    def test_resolve_name_does_not_use_final_snapshot_alias_before_it_exists(self) -> None:
        resolver = NameTimelineResolver.from_payload(
            {"captured_at": "2026-04-16T10:20:30+08:00", "bus": "session", "names": []},
            {
                "bus": "session",
                "started_at": "2026-04-16T10:20:30+08:00",
                "ended_at": "2026-04-16T10:20:40+08:00",
                "initial_snapshot": {},
                "events": [],
                "final_snapshot": {
                    "captured_at": "2026-04-16T10:20:40+08:00",
                    "bus": "session",
                    "names": [
                        {
                            "name": "org.example.LateService",
                            "owner": ":1.77",
                            "pid": 7777,
                            "uid": 1000,
                            "cmdline": ["/bin/late-service"],
                            "error": None,
                        }
                    ],
                },
                "error": None,
            },
        )

        resolved = resolver.resolve_name(":1.77", timestamp=1713243601.0)

        self.assertEqual(resolved.display_name, ":1.77")
        self.assertEqual(resolved.raw_name, ":1.77")
        self.assertIsNone(resolved.pid)


if __name__ == "__main__":
    unittest.main()
