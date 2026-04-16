from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path
from typing import Any
import zipfile


SUPPORTED_BUNDLE_VERSION = 1


@dataclass(frozen=True)
class BundleMetadata:
    bundle_version: int
    created_at: str
    bus: str
    duration_seconds: int
    capture_files: dict[str, str]
    monitor: dict[str, Any]
    extras: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "bundle_version": self.bundle_version,
            "created_at": self.created_at,
            "bus": self.bus,
            "duration_seconds": self.duration_seconds,
            "capture_files": self.capture_files,
            "monitor": self.monitor,
        }
        payload.update(self.extras)
        return payload

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> BundleMetadata:
        reserved = {
            "bundle_version",
            "created_at",
            "bus",
            "duration_seconds",
            "capture_files",
            "monitor",
        }
        return cls(
            bundle_version=int(payload["bundle_version"]),
            created_at=str(payload["created_at"]),
            bus=str(payload["bus"]),
            duration_seconds=int(payload["duration_seconds"]),
            capture_files=dict(payload["capture_files"]),
            monitor=dict(payload["monitor"]),
            extras={key: value for key, value in payload.items() if key not in reserved},
        )


@dataclass(frozen=True)
class BundleContents:
    metadata: BundleMetadata
    pcap_bytes: bytes
    profile_text: str
    names: dict[str, Any]


def is_bundle_path(path: Path) -> bool:
    return path.suffix == ".dblens"


def write_bundle(path: Path, contents: BundleContents) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("meta.json", json.dumps(contents.metadata.to_dict(), indent=2, sort_keys=True))
        archive.writestr(contents.metadata.capture_files["pcap"], contents.pcap_bytes)
        archive.writestr(contents.metadata.capture_files["profile"], contents.profile_text)
        archive.writestr(
            contents.metadata.capture_files["names"],
            json.dumps(contents.names, indent=2, sort_keys=True),
        )


def read_bundle(path: Path) -> BundleContents:
    with zipfile.ZipFile(path, "r") as archive:
        metadata = BundleMetadata.from_dict(json.loads(archive.read("meta.json")))
        if metadata.bundle_version != SUPPORTED_BUNDLE_VERSION:
            raise ValueError(f"unsupported bundle version: {metadata.bundle_version}")
        pcap_bytes = archive.read(metadata.capture_files["pcap"])
        profile_text = archive.read(metadata.capture_files["profile"]).decode("utf-8", "replace")
        names = json.loads(archive.read(metadata.capture_files["names"]))
    return BundleContents(
        metadata=metadata,
        pcap_bytes=pcap_bytes,
        profile_text=profile_text,
        names=names,
    )
