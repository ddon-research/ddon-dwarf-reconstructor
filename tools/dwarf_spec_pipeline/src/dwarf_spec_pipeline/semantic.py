"""Build a deterministic semantic index from the canonical DWARF documents.

The generated specification documents preserve the source text and tables, but a
converter can place an important table in a paragraph block.  This module adds
the small, query-oriented index needed by the reconstructor audit without
pretending that a normative "applicable" attribute list is a mandatory schema.
"""

from __future__ import annotations

import hashlib
import re
from collections import defaultdict
from pathlib import Path

from pydantic import Field

from .models import SpecificationDocument, StrictModel

_SYMBOL_RE = re.compile(r"\bDW_[A-Za-z0-9_]+\b")
_ATTRIBUTE_RE = re.compile(r"\bDW_AT_[A-Za-z0-9_]+\b")
_TAG_RE = re.compile(r"\bDW_TAG_[A-Za-z0-9_]+\b")
_ENCODING_RE = re.compile(
    r"(?P<name>DW_AT_[A-Za-z0-9_]+)\s+"
    r"(?P<value>0x[0-9A-Fa-f]+|-?[0-9]+)\s+"
    r"(?P<classes>.*?)(?=\s+DW_AT_[A-Za-z0-9_]+(?:\s|$)|$)",
    re.DOTALL,
)
_VALUE_RE = re.compile(r"^0x[0-9A-Fa-f]+$|^-?[0-9]+$")
_ATTRIBUTE_CLASSES = {
    "address",
    "block",
    "constant",
    "exprloc",
    "flag",
    "lineptr",
    "loclistptr",
    "macptr",
    "rangelistptr",
    "reference",
    "string",
}


class SemanticArtifact(StrictModel):
    """One canonical document used to derive the semantic index."""

    path: str
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class AttributeEncoding(StrictModel):
    """Normative attribute encoding facts observed in one DWARF version."""

    value: int | None
    value_text: str
    classes: list[str]
    source_tables: list[str]


class SemanticVersion(StrictModel):
    """Query-oriented facts for one specification version."""

    version: int
    namespaces: dict[str, list[str]]
    attribute_descriptions: dict[str, str]
    form_descriptions: dict[str, str]
    attribute_encodings: dict[str, AttributeEncoding]
    tag_applicability: dict[str, list[str]]


class SemanticIndex(StrictModel):
    """Stable cross-version DWARF vocabulary and relationship index."""

    schema_version: int = 1
    parser_version: str
    source_artifacts: list[SemanticArtifact]
    versions: list[SemanticVersion]
    cross_version: dict[str, dict[str, list[int]]]
    code_references: dict[str, dict[str, list[str]]]


def load_documents(
    output_dir: Path, versions: set[int] | None = None
) -> list[SpecificationDocument]:
    """Load the three checked-in canonical JSON documents."""
    import json

    documents: list[SpecificationDocument] = []
    selected_versions = versions or {2, 3, 4}
    for version in sorted(selected_versions):
        path = output_dir / f"dwarf{version}.json"
        documents.append(
            SpecificationDocument.model_validate(json.loads(path.read_text(encoding="utf-8")))
        )
    return documents


def build_semantic_index(
    documents: list[SpecificationDocument],
    *,
    source_root: Path | None = None,
    artifact_dir: Path | None = None,
) -> SemanticIndex:
    """Derive deterministic vocabulary, encodings, applicability, and code references."""
    versions = [
        _build_version(document)
        for document in sorted(documents, key=lambda item: item.specification.version)
    ]
    artifacts = _source_artifacts(documents, artifact_dir)
    return SemanticIndex(
        parser_version=max((document.parser_version for document in documents), default="unknown"),
        source_artifacts=artifacts,
        versions=versions,
        cross_version=_cross_version(versions),
        code_references=_code_references(source_root) if source_root else {},
    )


def _build_version(document: SpecificationDocument) -> SemanticVersion:
    text = _document_text(document)
    namespaces: defaultdict[str, set[str]] = defaultdict(set)
    for symbol in _SYMBOL_RE.findall(text):
        namespaces[_namespace(symbol)].add(symbol)
    descriptions = _attribute_descriptions(document)
    form_descriptions = _form_descriptions(document)
    return SemanticVersion(
        version=document.specification.version,
        namespaces={key: sorted(values) for key, values in sorted(namespaces.items())},
        attribute_descriptions=dict(sorted(descriptions.items())),
        form_descriptions=dict(sorted(form_descriptions.items())),
        attribute_encodings=dict(sorted(_attribute_encodings(document).items())),
        tag_applicability=dict(sorted(_tag_applicability(document).items())),
    )


def _document_text(document: SpecificationDocument) -> str:
    parts: list[str] = []
    for section in document.sections:
        parts.append(section.title)
        for block in section.blocks:
            if hasattr(block, "text"):
                parts.append(block.text)
            elif hasattr(block, "items"):
                parts.extend(block.items)
    for table in document.tables:
        parts.append(" ".join(table.headers))
        parts.extend(" ".join(row) for row in table.rows)
    return "\n".join(parts)


def _namespace(symbol: str) -> str:
    parts = symbol.split("_", 2)
    return "_".join(parts[:2]) if len(parts) > 1 else symbol


def _attribute_descriptions(document: SpecificationDocument) -> dict[str, str]:
    descriptions: dict[str, str] = {}
    for table in document.tables:
        headers = [header.lower() for header in table.headers]
        name_index = _header_index(headers, ("attribute",))
        description_index = _header_index(headers, ("identifies", "specifies"))
        if name_index is None or description_index is None:
            continue
        for row in table.rows:
            if len(row) <= max(name_index, description_index):
                continue
            name = row[name_index].strip()
            if name.startswith("DW_AT_"):
                descriptions[name] = row[description_index].strip()
    return descriptions


def _form_descriptions(document: SpecificationDocument) -> dict[str, str]:
    descriptions: dict[str, str] = {}
    for table in document.tables:
        headers = [header.lower() for header in table.headers]
        name_index = _header_index(headers, ("attribute", "class"))
        description_index = _header_index(headers, ("general", "use"))
        if name_index is None or description_index is None:
            continue
        for row in table.rows:
            if len(row) <= max(name_index, description_index):
                continue
            name = row[name_index].strip()
            if name:
                descriptions[name] = row[description_index].strip()
    return descriptions


def _header_index(headers: list[str], words: tuple[str, ...]) -> int | None:
    for index, header in enumerate(headers):
        if all(word in header for word in words):
            return index
    return None


def _attribute_encodings(document: SpecificationDocument) -> dict[str, AttributeEncoding]:
    records: dict[str, AttributeEncoding] = {}
    for table in document.tables:
        headers = [header.lower() for header in table.headers]
        name_index = _header_index(headers, ("attribute", "name"))
        value_index = _header_index(headers, ("value",))
        classes_index = _header_index(headers, ("class",))
        if name_index is None or value_index is None or classes_index is None:
            continue
        for row in table.rows:
            if len(row) <= max(name_index, value_index, classes_index):
                continue
            name = row[name_index].strip()
            value_text = row[value_index].strip()
            if name.startswith("DW_AT_") and _VALUE_RE.fullmatch(value_text):
                _merge_encoding(records, name, value_text, row[classes_index], table.id)
    for section in document.sections:
        if "attribute encoding" not in section.title.lower():
            continue
        for block in section.blocks:
            text = getattr(block, "text", "")
            for match in _ENCODING_RE.finditer(text):
                _merge_encoding(
                    records,
                    match.group("name"),
                    match.group("value"),
                    match.group("classes"),
                    f"section:{section.id}",
                )
    return records


def _merge_encoding(
    records: dict[str, AttributeEncoding],
    name: str,
    value_text: str,
    class_text: str,
    source: str,
) -> None:
    try:
        value = int(value_text, 0) if value_text.lower().startswith("0x") else int(value_text)
    except ValueError:
        value = None
    classes = sorted(
        {token for token in re.findall(r"[a-z]+", class_text) if token in _ATTRIBUTE_CLASSES}
    )
    previous = records.get(name)
    if previous is None:
        records[name] = AttributeEncoding(
            value=value,
            value_text=value_text,
            classes=classes,
            source_tables=[source],
        )
        return
    records[name] = AttributeEncoding(
        value=previous.value,
        value_text=previous.value_text,
        classes=sorted(set(previous.classes) | set(classes)),
        source_tables=sorted(set(previous.source_tables) | {source}),
    )


def _tag_applicability(document: SpecificationDocument) -> dict[str, list[str]]:
    records: dict[str, set[str]] = defaultdict(set)
    for table in document.tables:
        headers = [header.lower() for header in table.headers]
        tag_index = _header_index(headers, ("tag", "name"))
        attributes_index = _header_index(headers, ("applicable", "attribute"))
        if tag_index is None or attributes_index is None:
            continue
        for row in table.rows:
            if len(row) <= max(tag_index, attributes_index):
                continue
            tag = row[tag_index].strip()
            if tag.startswith("DW_TAG_"):
                records[tag].update(_ATTRIBUTE_RE.findall(row[attributes_index]))
    for section in document.sections:
        if "current attributes by tag" not in section.title.lower():
            continue
        for block in section.blocks:
            text = getattr(block, "text", "")
            matches = list(_TAG_RE.finditer(text))
            for index, match in enumerate(matches):
                end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
                records[match.group()].update(_ATTRIBUTE_RE.findall(text[match.end() : end]))
    return {tag: sorted(attributes) for tag, attributes in sorted(records.items())}


def _source_artifacts(
    documents: list[SpecificationDocument], artifact_dir: Path | None
) -> list[SemanticArtifact]:
    artifacts: list[SemanticArtifact] = []
    if artifact_dir is None:
        return artifacts
    for document in sorted(documents, key=lambda item: item.specification.version):
        path = artifact_dir / f"dwarf{document.specification.version}.json"
        artifacts.append(
            SemanticArtifact(
                path=path.name,
                sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
            )
        )
    return artifacts


def _cross_version(versions: list[SemanticVersion]) -> dict[str, dict[str, list[int]]]:
    presence: defaultdict[str, defaultdict[str, list[int]]] = defaultdict(lambda: defaultdict(list))
    for version in versions:
        for namespace, symbols in version.namespaces.items():
            for symbol in symbols:
                presence[namespace][symbol].append(version.version)
    return {
        namespace: {
            symbol: sorted(version_numbers) for symbol, version_numbers in sorted(symbols.items())
        }
        for namespace, symbols in sorted(presence.items())
    }


def _code_references(source_root: Path) -> dict[str, dict[str, list[str]]]:
    references: defaultdict[str, defaultdict[str, set[str]]] = defaultdict(lambda: defaultdict(set))
    for path in sorted(source_root.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        relative = path.relative_to(source_root).as_posix()
        for symbol in sorted(set(_SYMBOL_RE.findall(text))):
            references[_namespace(symbol)][symbol].add(relative)
    return {
        namespace: {symbol: sorted(paths) for symbol, paths in sorted(symbols.items())}
        for namespace, symbols in sorted(references.items())
    }


def render_markdown(index: SemanticIndex) -> str:
    """Render the semantic index as a compact reviewable report."""
    lines = [
        "# DWARF 2/3/4 Semantic Index",
        "",
        f"> Schema: `{index.schema_version}`; parser: `{index.parser_version}`",
        "",
        "## Version inventory",
        "",
        "| Version | Tags | Attributes | Forms | Operations | Languages |",
        "| ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for version in index.versions:
        lines.append(
            "| {version} | {tags} | {attributes} | {forms} | {operations} | {languages} |".format(
                version=version.version,
                tags=len(version.namespaces.get("DW_TAG", [])),
                attributes=len(version.namespaces.get("DW_AT", [])),
                forms=len(version.namespaces.get("DW_FORM", [])),
                operations=len(version.namespaces.get("DW_OP", [])),
                languages=len(version.namespaces.get("DW_LANG", [])),
            )
        )
    lines.extend(["", "## High-risk relationship checks", ""])
    for version in index.versions:
        containing = version.tag_applicability.get("DW_TAG_ptr_to_member_type", [])
        class_attributes = version.tag_applicability.get("DW_TAG_class_type", [])
        high_pc = version.attribute_encodings.get("DW_AT_high_pc")
        lines.append(f"### DWARF {version.version}")
        lines.append(
            f"- `DW_AT_containing_type` applies to `DW_TAG_ptr_to_member_type`: "
            f"`{'DW_AT_containing_type' in containing}`."
        )
        lines.append(
            f"- `DW_AT_containing_type` applies to `DW_TAG_class_type`: "
            f"`{'DW_AT_containing_type' in class_attributes}`."
        )
        if high_pc is not None:
            lines.append(f"- `DW_AT_high_pc` classes: `{', '.join(high_pc.classes)}`.")
        lines.append("")
    lines.extend(["## Attribute encodings", ""])
    for version in index.versions:
        lines.extend(
            [
                f"### DWARF {version.version}",
                "",
                "| Attribute | Value | Classes |",
                "| --- | ---: | --- |",
            ]
        )
        for name, encoding in version.attribute_encodings.items():
            lines.append(f"| `{name}` | `{encoding.value_text}` | {', '.join(encoding.classes)} |")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def write_index(index: SemanticIndex, json_path: Path, markdown_path: Path) -> None:
    """Publish both report formats after rendering them completely."""
    import json

    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(
        json.dumps(index.model_dump(mode="json"), ensure_ascii=False, indent=2, sort_keys=True)
        + "\n",
        encoding="utf-8",
        newline="\n",
    )
    markdown_path.write_text(render_markdown(index), encoding="utf-8", newline="\n")
