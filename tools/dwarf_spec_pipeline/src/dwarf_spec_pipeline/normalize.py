"""Public normalization facade for the DWARF specification pipeline."""

from .document_builder import DocumentBuilder, build_document, source_metadata

__all__ = ["DocumentBuilder", "build_document", "source_metadata"]
