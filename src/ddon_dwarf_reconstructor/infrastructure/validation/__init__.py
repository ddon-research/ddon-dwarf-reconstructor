"""Optional implementation-validation feature boundary.

Normal generation does not import this package. The package owns adapters
that turn validation results into generic evidence overlays when a caller
explicitly elects to publish them. Submodules are intentionally not imported
here, so selecting the package does not eagerly load strict validation or
external-tool dependencies.
"""

__all__ = []
