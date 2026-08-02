"""Atomic publication of generated header bundles."""

from __future__ import annotations

import hashlib
import json
import logging
import os
import shutil
import tempfile
from collections.abc import Mapping
from pathlib import Path
from time import perf_counter

from ..core.observability import get_logger, log_event
from ..core.platform import ELFPlatform

logger = get_logger(__name__)


class AtomicHeaderPublisher:
    """Stage, publish, and describe a generated header bundle."""

    MANIFEST_NAME = "header-bundle.manifest.json"

    def publish(
        self, output_root: Path, platform: ELFPlatform, headers: Mapping[str, str]
    ) -> tuple[Path, int]:
        platform_dir = output_root / platform.value
        platform_dir.mkdir(parents=True, exist_ok=True)
        staged_dir = Path(tempfile.mkdtemp(prefix=".headers-", dir=platform_dir))
        backup_dir = Path(tempfile.mkdtemp(prefix=".headers-backup-", dir=platform_dir))
        manifest_path = platform_dir / self.MANIFEST_NAME
        targets: list[str] = []
        backups: dict[str, Path | None] = {}
        manifest_backup: Path | None = None
        started_at = perf_counter()
        log_event(
            logger,
            logging.DEBUG,
            "header_bundle_publish_started",
            output_dir=platform_dir,
            platform=platform.value,
            header_count=len(headers),
        )
        try:
            new_filenames = self._stage_headers(staged_dir, headers)
            targets = sorted({*new_filenames, *self._previous_filenames(manifest_path)})
            backups = self._backup_targets(backup_dir, platform_dir, targets)
            manifest_backup = self._backup_manifest(backup_dir, manifest_path)
            for filename in new_filenames:
                os.replace(staged_dir / filename, platform_dir / filename)
            for filename in targets:
                if filename not in headers:
                    (platform_dir / filename).unlink(missing_ok=True)
            self._publish_manifest(staged_dir, manifest_path, headers)
        except Exception as error:
            log_event(
                logger,
                logging.ERROR,
                "header_bundle_publish_failed",
                output_dir=platform_dir,
                platform=platform.value,
                header_count=len(headers),
                duration_ms=round((perf_counter() - started_at) * 1000, 3),
                exc_info=error,
            )
            self._rollback(platform_dir, backups, manifest_path, manifest_backup)
            raise
        except BaseException:
            self._rollback(platform_dir, backups, manifest_path, manifest_backup)
            raise
        finally:
            shutil.rmtree(staged_dir, ignore_errors=True)
            shutil.rmtree(backup_dir, ignore_errors=True)
        total_bytes = sum(len(content.encode("utf-8")) for content in headers.values())
        log_event(
            logger,
            logging.INFO,
            "header_bundle_published",
            output_dir=platform_dir,
            platform=platform.value,
            header_count=len(headers),
            total_bytes=total_bytes,
            duration_ms=round((perf_counter() - started_at) * 1000, 3),
        )
        return platform_dir, total_bytes

    @classmethod
    def _previous_filenames(cls, manifest_path: Path) -> list[str]:
        if not manifest_path.exists():
            return []
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise ValueError(f"Cannot read existing header manifest: {manifest_path}") from error
        files = manifest.get("files") if isinstance(manifest, dict) else None
        if not isinstance(files, dict):
            raise ValueError(f"Existing header manifest has no files map: {manifest_path}")
        filenames = sorted(files)
        for filename in filenames:
            if Path(filename).name != filename or Path(filename).is_absolute():
                raise ValueError(f"Manifest contains an unsafe header filename: {filename!r}")
        return filenames

    @staticmethod
    def _stage_headers(staged_dir: Path, headers: Mapping[str, str]) -> list[str]:
        filenames = sorted(headers)
        for filename in filenames:
            if Path(filename).name != filename or Path(filename).is_absolute():
                raise ValueError(f"Header filename must be a single relative name: {filename!r}")
            path = staged_dir / filename
            path.write_text(headers[filename], encoding="utf-8", newline="\n")
        return filenames

    @staticmethod
    def _backup_targets(
        backup_dir: Path, platform_dir: Path, filenames: list[str]
    ) -> dict[str, Path | None]:
        backups: dict[str, Path | None] = {}
        for filename in filenames:
            target = platform_dir / filename
            if not target.exists():
                backups[filename] = None
                continue
            backup = backup_dir / filename
            shutil.copy2(target, backup)
            backups[filename] = backup
        return backups

    @staticmethod
    def _backup_manifest(backup_dir: Path, manifest_path: Path) -> Path | None:
        if not manifest_path.exists():
            return None
        backup = backup_dir / manifest_path.name
        shutil.copy2(manifest_path, backup)
        return backup

    def _publish_manifest(
        self, staged_dir: Path, manifest_path: Path, headers: Mapping[str, str]
    ) -> None:
        manifest = {
            "files": {
                filename: {
                    "bytes": len(content.encode("utf-8")),
                    "sha256": hashlib.sha256(content.encode("utf-8")).hexdigest(),
                }
                for filename, content in sorted(headers.items())
            }
        }
        staged_manifest = staged_dir / self.MANIFEST_NAME
        staged_manifest.write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        os.replace(staged_manifest, manifest_path)

    @staticmethod
    def _rollback(
        platform_dir: Path,
        backups: Mapping[str, Path | None],
        manifest_path: Path,
        manifest_backup: Path | None,
    ) -> None:
        for filename, backup in backups.items():
            target = platform_dir / filename
            if backup is None:
                target.unlink(missing_ok=True)
            else:
                os.replace(backup, target)
        if manifest_backup is None:
            manifest_path.unlink(missing_ok=True)
        else:
            os.replace(manifest_backup, manifest_path)
