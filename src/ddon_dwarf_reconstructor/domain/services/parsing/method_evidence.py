"""Method-implementation evidence scoring and parameter-name merging."""

from ....core.dwarf import DwarfEntry, decode_dwarf_string
from ....core.observability import get_logger
from ...models.dwarf import ParameterInfo

logger = get_logger(__name__)


def score_implementation(implementation: DwarfEntry) -> int:
    """Score implementation evidence while traversing children once."""
    named_parameters = 0
    lexical_blocks = 0
    for child in implementation.iter_children():
        if child.tag == "DW_TAG_formal_parameter" and "DW_AT_name" in child.attributes:
            named_parameters += 1
        elif child.tag == "DW_TAG_lexical_block":
            lexical_blocks += 1

    return (
        (1000 if "DW_AT_low_pc" in implementation.attributes else 0)
        + named_parameters * 100
        + (50 if "DW_AT_inline" in implementation.attributes else 0)
        + lexical_blocks * 10
    )


def merge_parameter_names(
    implementation: DwarfEntry,
    declaration_parameters: list[ParameterInfo],
    method_name: str,
) -> int:
    """Merge proven implementation parameter names into declaration models."""
    implementation_names = _implementation_parameter_names(implementation)
    declaration_targets = _declaration_parameters(declaration_parameters)
    merge_count = min(len(implementation_names), len(declaration_targets))
    _log_parameter_count(method_name, implementation_names, declaration_targets)
    _apply_parameter_names(declaration_targets, implementation_names, merge_count)
    if merge_count:
        logger.debug(f"Merged {merge_count} parameter names for {method_name}")
    return merge_count


def _implementation_parameter_names(implementation: DwarfEntry) -> list[str]:
    names: list[str] = []
    for child in implementation.iter_children():
        if child.tag != "DW_TAG_formal_parameter":
            continue
        if "DW_AT_artificial" in child.attributes:
            continue
        name_attribute = child.attributes.get("DW_AT_name")
        if name_attribute:
            names.append(decode_dwarf_string(name_attribute.value))
    return names


def _declaration_parameters(declaration_parameters: list[ParameterInfo]) -> list[ParameterInfo]:
    return [parameter for parameter in declaration_parameters if parameter.name != "__artificial__"]


def _log_parameter_count(
    method_name: str, implementation_names: list[str], declaration_targets: list[ParameterInfo]
) -> None:
    if len(implementation_names) != len(declaration_targets):
        logger.warning(
            f"Parameter count mismatch for {method_name}: "
            f"implementation has {len(implementation_names)} params, "
            f"declaration has {len(declaration_targets)} non-artificial params"
        )


def _apply_parameter_names(
    declaration_targets: list[ParameterInfo], implementation_names: list[str], merge_count: int
) -> None:
    for parameter, implementation_name in zip(
        declaration_targets[:merge_count], implementation_names[:merge_count], strict=True
    ):
        old_name = parameter.name
        parameter.name = implementation_name
        if old_name.startswith("param"):
            logger.debug(f"  {old_name} -> {parameter.name}")
