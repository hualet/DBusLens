import tempfile
import unittest
from pathlib import Path

from dbuslens.bundle import BundleContents, BundleMetadata, read_bundle, write_bundle


class BundleRoundTripTests(unittest.TestCase):
    def test_write_and_read_bundle_round_trip(self) -> None:
        metadata = BundleMetadata(
            bundle_version=1,
            created_at="2026-04-16T10:20:30+08:00",
            bus="session",
            duration_seconds=10,
            capture_files={
                "pcap": "capture.cap",
                "profile": "capture.profile",
                "names": "names.json",
            },
            monitor={
                "command": ["dbus-monitor", "--session", "--pcap"],
                "profile_command": ["dbus-monitor", "--session", "--profile"],
                "stderr": "",
                "mode": "monitor",
            },
            extras={"notes": "test"},
        )
        expected = BundleContents(
            metadata=metadata,
            pcap_bytes=b"pcap-bytes",
            profile_text="profile-text",
            names={"captured_at": "2026-04-16T10:20:31+08:00", "names": []},
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "sample.dblens"

            write_bundle(path, expected)
            actual = read_bundle(path)

        self.assertEqual(actual.metadata, metadata)
        self.assertEqual(actual.pcap_bytes, b"pcap-bytes")
        self.assertEqual(actual.profile_text, "profile-text")
        self.assertEqual(actual.names, {"captured_at": "2026-04-16T10:20:31+08:00", "names": []})

    def test_read_bundle_rejects_unsupported_version(self) -> None:
        metadata = BundleMetadata(
            bundle_version=99,
            created_at="2026-04-16T10:20:30+08:00",
            bus="session",
            duration_seconds=10,
            capture_files={
                "pcap": "capture.cap",
                "profile": "capture.profile",
                "names": "names.json",
            },
            monitor={
                "command": ["dbus-monitor", "--session", "--pcap"],
                "profile_command": ["dbus-monitor", "--session", "--profile"],
                "stderr": "",
                "mode": "monitor",
            },
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "sample.dblens"
            write_bundle(
                path,
                BundleContents(
                    metadata=metadata,
                    pcap_bytes=b"pcap-bytes",
                    profile_text="profile-text",
                    names={"captured_at": "2026-04-16T10:20:31+08:00", "names": []},
                ),
            )

            with self.assertRaisesRegex(ValueError, "unsupported bundle version"):
                read_bundle(path)


if __name__ == "__main__":
    unittest.main()
