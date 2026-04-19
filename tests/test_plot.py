import tempfile
import unittest
from argparse import Namespace
from pathlib import Path
from unittest.mock import patch

from dbus_fast.constants import MessageType
from dbus_fast.message import Message

from dbuslens.bundle import BundleContents, BundleMetadata, write_bundle
from dbuslens.cli import _handle_plot, build_parser
from dbuslens.models import Event
from dbuslens.plot import build_dependency_dot, render_graphviz_output
from tests.test_pcap_parser import build_pcap_bytes


class PlotTests(unittest.TestCase):
    def test_build_parser_defines_plot_subcommand(self) -> None:
        parser = build_parser()

        args = parser.parse_args(["plot"])

        self.assertEqual(args.command, "plot")
        self.assertEqual(args.input, "record.dblens")
        self.assertIsNone(args.output)
        self.assertEqual(args.format, "svg")
        self.assertEqual(args.raw, False)

    def test_build_dependency_dot_simplifies_unique_names_and_filters_dbus_noise(self) -> None:
        dot = build_dependency_dot(
            [
                Event(
                    timestamp=1.0,
                    message_type="method_call",
                    sender=":1.10",
                    destination=":1.42",
                    path="/org/example/Demo",
                    interface="org.example.Demo",
                    member="Ping",
                    serial=1,
                    reply_serial=None,
                    error_name=None,
                ),
                Event(
                    timestamp=2.0,
                    message_type="method_call",
                    sender=":1.11",
                    destination=":1.42",
                    path="/org/example/Demo",
                    interface="org.example.Demo",
                    member="Echo",
                    serial=2,
                    reply_serial=None,
                    error_name=None,
                ),
                Event(
                    timestamp=3.0,
                    message_type="method_call",
                    sender=":1.10",
                    destination="org.freedesktop.DBus",
                    path="/org/freedesktop/DBus",
                    interface="org.freedesktop.DBus",
                    member="Hello",
                    serial=3,
                    reply_serial=None,
                    error_name=None,
                ),
            ],
            snapshot_names={
                "captured_at": "2026-04-19T10:20:31+08:00",
                "bus": "session",
                "names": [
                    {
                        "name": "org.example.Client",
                        "owner": ":1.10",
                        "pid": 1010,
                        "uid": 1000,
                        "cmdline": ["/usr/bin/example-client"],
                        "error": None,
                    },
                    {
                        "name": "org.example.Service",
                        "owner": ":1.42",
                        "pid": 2020,
                        "uid": 1000,
                        "cmdline": ["/usr/bin/example-service"],
                        "error": None,
                    },
                ],
            },
            min_count=1,
        )

        self.assertIn('"org.example.Client" -> "org.example.Service" [label="1"', dot)
        self.assertNotIn('":1.11"', dot)
        self.assertNotIn("org.freedesktop.DBus", dot)
        self.assertIn("digraph dbus_dependencies {", dot)

    def test_build_dependency_dot_raw_mode_keeps_unique_names(self) -> None:
        dot = build_dependency_dot(
            [
                Event(
                    timestamp=1.0,
                    message_type="method_call",
                    sender=":1.10",
                    destination="org.example.Service",
                    path="/org/example/Demo",
                    interface="org.example.Demo",
                    member="Ping",
                    serial=1,
                    reply_serial=None,
                    error_name=None,
                ),
                Event(
                    timestamp=2.0,
                    message_type="method_call",
                    sender=":1.10",
                    destination="org.example.Service",
                    path="/org/example/Demo",
                    interface="org.example.Demo",
                    member="Echo",
                    serial=2,
                    reply_serial=None,
                    error_name=None,
                ),
            ],
            raw=True,
        )

        self.assertIn('":1.10" -> "org.example.Service" [label="2"', dot)

    def test_build_dependency_dot_keeps_single_edge_by_default(self) -> None:
        dot = build_dependency_dot(
            [
                Event(
                    timestamp=1.0,
                    message_type="method_call",
                    sender="org.example.Client",
                    destination="org.example.Service",
                    path="/org/example/Demo",
                    interface="org.example.Demo",
                    member="Ping",
                    serial=1,
                    reply_serial=None,
                    error_name=None,
                )
            ]
        )

        self.assertIn('"org.example.Client" -> "org.example.Service" [label="1"', dot)

    def test_build_dependency_dot_hides_unresolved_unique_names_in_simplified_mode(self) -> None:
        dot = build_dependency_dot(
            [
                Event(
                    timestamp=1.0,
                    message_type="method_call",
                    sender=":1.10",
                    destination="org.example.Service",
                    path="/org/example/Demo",
                    interface="org.example.Demo",
                    member="Ping",
                    serial=1,
                    reply_serial=None,
                    error_name=None,
                ),
                Event(
                    timestamp=2.0,
                    message_type="method_call",
                    sender="org.example.Service",
                    destination=":1.11",
                    path="/org/example/Demo",
                    interface="org.example.Demo",
                    member="Callback",
                    serial=2,
                    reply_serial=None,
                    error_name=None,
                ),
            ],
            min_count=1,
        )

        self.assertNotIn('":1.10"', dot)
        self.assertNotIn('":1.11"', dot)
        self.assertNotIn("->", dot)

    def test_build_dependency_dot_includes_project_theme_attributes(self) -> None:
        dot = build_dependency_dot(
            [
                Event(
                    timestamp=1.0,
                    message_type="method_call",
                    sender="org.example.Client",
                    destination="org.example.Service",
                    path="/org/example/Demo",
                    interface="org.example.Demo",
                    member="Ping",
                    serial=1,
                    reply_serial=None,
                    error_name=None,
                )
            ]
        )

        self.assertIn('bgcolor="#080a0f"', dot)
        self.assertIn('color="#6ee7b7"', dot)
        self.assertIn('fontcolor="#fcd34d"', dot)

    def test_render_graphviz_output_uses_dot_command(self) -> None:
        with patch("dbuslens.plot.subprocess.run") as run:
            run.return_value.stdout = b"<svg>ok</svg>"
            run.return_value.stderr = b""

            rendered = render_graphviz_output("digraph { a -> b; }\n", output_format="svg")

        self.assertEqual(rendered, "<svg>ok</svg>")
        run.assert_called_once()
        command = run.call_args.args[0]
        self.assertEqual(command, ["dot", "-Tsvg"])

    def test_handle_plot_writes_dot_output(self) -> None:
        capture = build_pcap_bytes(
            [
                (
                    1.0,
                    Message(
                        message_type=MessageType.METHOD_CALL,
                        sender=":1.10",
                        destination="org.example.Service",
                        path="/org/example/Demo",
                        interface="org.example.Demo",
                        member="Ping",
                        serial=1,
                    ),
                ),
                (
                    2.0,
                    Message(
                        message_type=MessageType.METHOD_CALL,
                        sender=":1.10",
                        destination="org.example.Service",
                        path="/org/example/Demo",
                        interface="org.example.Demo",
                        member="Echo",
                        serial=2,
                    ),
                ),
            ]
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            input_path = Path(tmpdir) / "sample.dblens"
            output_path = Path(tmpdir) / "graph.dot"
            write_bundle(
                input_path,
                BundleContents(
                    metadata=BundleMetadata(
                        bundle_version=1,
                        created_at="2026-04-19T10:20:30+08:00",
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
                    ),
                    pcap_bytes=capture,
                    profile_text="",
                    names={"captured_at": "2026-04-19T10:20:31+08:00", "bus": "session", "names": []},
                ),
            )

            exit_code = _handle_plot(
                Namespace(input=str(input_path), output=str(output_path), format="dot", raw=True)
            )

            self.assertEqual(exit_code, 0)
            self.assertIn('":1.10" -> "org.example.Service" [label="2"', output_path.read_text())

    def test_handle_plot_uses_default_output_path_from_input(self) -> None:
        capture = build_pcap_bytes(
            [
                (
                    1.0,
                    Message(
                        message_type=MessageType.METHOD_CALL,
                        sender="org.example.Client",
                        destination="org.example.Service",
                        path="/org/example/Demo",
                        interface="org.example.Demo",
                        member="Ping",
                        serial=1,
                    ),
                ),
            ]
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            input_path = Path(tmpdir) / "sample.dblens"
            default_output_path = Path(tmpdir) / "sample.svg"
            write_bundle(
                input_path,
                BundleContents(
                    metadata=BundleMetadata(
                        bundle_version=1,
                        created_at="2026-04-19T10:20:30+08:00",
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
                    ),
                    pcap_bytes=capture,
                    profile_text="",
                    names={"captured_at": "2026-04-19T10:20:31+08:00", "bus": "session", "names": []},
                ),
            )

            with patch("dbuslens.cli.render_graphviz_output", return_value="<svg>ok</svg>"):
                exit_code = _handle_plot(
                    Namespace(input=str(input_path), output=None, format="svg", raw=False)
                )

            self.assertEqual(exit_code, 0)
            self.assertTrue(default_output_path.exists())
            self.assertEqual(default_output_path.read_text(), "<svg>ok</svg>")


if __name__ == "__main__":
    unittest.main()
