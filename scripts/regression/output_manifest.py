"""Create and compare deterministic output manifests.

Header bytes are compared exactly.  Other files are included only when their
extensions are explicitly requested, allowing callers to exclude volatile
runtime metadata while keeping the comparison policy visible.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

DEFAULT_EXTENSIONS = (".h", ".hpp")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_manifest(
    root: Path,
    *,
    extensions: tuple[str, ...] = DEFAULT_EXTENSIONS,
    source: Path | None = None,
    command: str | None = None,
    producer: str | None = None,
    configuration: dict[str, Any] | None = None,
    cache_state: str | None = None,
) -> dict[str, Any]:
    normalized_extensions = tuple(extension.lower() for extension in extensions)
    files: dict[str, dict[str, Any]] = {}
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in normalized_extensions:
            continue
        relative = path.relative_to(root).as_posix()
        files[relative] = {"bytes": path.stat().st_size, "sha256": sha256_file(path)}
    result: dict[str, Any] = {
        "root": str(root.resolve()),
        "extensions": list(normalized_extensions),
        "files": files,
    }
    if source is not None:
        result["source"] = {
            "path": str(source.resolve()),
            "bytes": source.stat().st_size,
            "sha256": sha256_file(source),
        }
    if command is not None:
        result["command"] = command
    if producer is not None:
        result["producer"] = producer
    if configuration is not None:
        result["configuration"] = configuration
    if cache_state is not None:
        result["cache_state"] = cache_state
    return result


def write_manifest(manifest: dict[str, Any], destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def compare_manifests(expected: dict[str, Any], actual: dict[str, Any]) -> list[str]:
    differences: list[str] = []
    expected_files = expected.get("files", {})
    actual_files = actual.get("files", {})
    for relative in sorted(set(expected_files) | set(actual_files)):
        if relative not in expected_files:
            differences.append(f"unexpected output: {relative}")
        elif relative not in actual_files:
            differences.append(f"missing output: {relative}")
        elif expected_files[relative] != actual_files[relative]:
            differences.append(
                f"changed output: {relative}: expected {expected_files[relative]}, "
                f"actual {actual_files[relative]}"
            )
    return differences


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="action", required=True)

    create = subparsers.add_parser("create")
    create.add_argument("root", type=Path)
    create.add_argument("manifest", type=Path)
    create.add_argument("--source", type=Path)
    create.add_argument("--extensions", default=",".join(DEFAULT_EXTENSIONS))
    create.add_argument("--producer")
    create.add_argument("--cache-state")
    create.add_argument("--command")
    create.add_argument(
        "--configuration-json",
        type=Path,
        help="JSON object describing output-affecting configuration",
    )

    compare = subparsers.add_parser("compare")
    compare.add_argument("expected", type=Path)
    compare.add_argument("actual", type=Path)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.action == "create":
        extensions = tuple(item.strip() for item in args.extensions.split(",") if item.strip())
        configuration = None
        if args.configuration_json is not None:
            configuration = json.loads(
                args.configuration_json.read_text(encoding="utf-8")
            )
        manifest = build_manifest(
            args.root,
            extensions=extensions,
            source=args.source,
            command=args.command,
            producer=args.producer,
            configuration=configuration,
            cache_state=args.cache_state,
        )
        write_manifest(manifest, args.manifest)
        return 0

    expected = json.loads(args.expected.read_text(encoding="utf-8"))
    actual = json.loads(args.actual.read_text(encoding="utf-8"))
    differences = compare_manifests(expected, actual)
    for difference in differences:
        print(difference)
    if differences:
        return 1
    print("Output manifests match.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
