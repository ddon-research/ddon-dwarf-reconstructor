# PS3 DWARF2 Critical Issue: Location Expressions

**Date:** October 19, 2025  
**Status:** BLOCKING - Must fix before PS3 support works  
**Severity:** HIGH

## Summary

PS3 uses DWARF2 with `DW_FORM_block1` for member location encoding, returning DWARF location expressions (lists) like `[35, 4]` instead of simple integer offsets used in PS4 DWARF3/4.

## The Problem

### PS4 DWARF3/4 (Currently Supported)

```python
DW_AT_data_member_location = AttributeValue(
    form='DW_FORM_data4',
    value=4,  # <-- Direct integer offset
    ...
)
```

Code expects:
```python
member.offset = 4  # Integer
```

### PS3 DWARF2 (NEW - Currently Breaks)

```python
DW_AT_data_member_location = AttributeValue(
    form='DW_FORM_block1',
    value=[35, 4],  # <-- DWARF location expression (opcodes + data)
    ...
)
```

Code expects integer but receives list:
```python
member.offset = [35, 4]  # ListContainer - causes TypeError!
```

The list `[35, 4]` is a DWARF location expression where:
- `35` = `DW_OP_plus_uconst` opcode (add unsigned constant)
- `4` = the constant value (the actual member offset!)

## Error Trace

```
File "packing_analyzer.py", line 65, in calculate_packing_info
    expected_offset = last_offset + last_size
                      ~~~~~~~~~~~~^~~~~~~~~~~
TypeError: can only concatenate list (not "int") to list
```

Because `last_offset` is `[35, 4]` (list), not `4` (int).

## Impact Analysis

### Affected Code Paths

1. **ClassParser** (`src/ddon_dwarf_reconstructor/generators/utils/class_parser.py`)
   - `parse_members()` - extracts member offsets from DIE
   - Line: Wherever it sets `member.offset`

2. **MemberInfo** (model)
   - `offset` field - expects `int`, receives `list`

3. **PackingAnalyzer** (`src/ddon_dwarf_reconstructor/generators/utils/packing_analyzer.py`)
   - `calculate_packing_info()` - fails when using list offsets
   - Assumes all `member.offset` values are integers

4. **HeaderGenerator**
   - May have layout calculation issues downstream

5. **DependencyExtractor** 
   - May use member offsets

### Cascading Failures

```
DwarfGenerator.generate_header("MtDTI")
  └─> parse_class_info()
        └─> ClassParser.parse_members()  <-- Sets offset to [35, 4]
        └─> calculate_packing_info()     <-- CRASHES: can't add list + int
```

## Solution Strategy

### Step 1: Parse Location Expressions

Create a helper function to extract offset from DWARF location expressions:

```python
def parse_location_offset(attr_value) -> int | None:
    """Extract member offset from DW_AT_data_member_location.
    
    Handles both forms:
    - Integer offsets (PS4 DWARF3/4): DW_FORM_data4 -> returns int
    - Location expressions (PS3 DWARF2): DW_FORM_block1 -> returns [opcode, ...]
    
    Returns:
        Integer offset, or None if cannot parse
    """
    if attr_value is None:
        return None
    
    # Already an integer (PS4 style)
    if isinstance(attr_value, int):
        return attr_value
    
    # Location expression (PS3 style)
    if isinstance(attr_value, (list, tuple)):
        # DWARF location expressions: [opcode, arg1, arg2, ...]
        # DW_OP_plus_uconst (0x23) = 35: offset = next value
        if len(attr_value) >= 2 and attr_value[0] == 0x23:  # DW_OP_plus_uconst
            return attr_value[1]
        
        # If it's just [offset] or similar simple form
        if len(attr_value) == 1 and isinstance(attr_value[0], int):
            return attr_value[0]
    
    # Unknown format
    return None
```

### Step 2: Update Member Parsing

In `ClassParser.parse_members()`, replace:
```python
# OLD
member.offset = member_attr.value

# NEW
member.offset = parse_location_offset(member_attr.value)
```

### Step 3: Add Validation

Ensure all tests pass with both PS3 and PS4 data.

## Reference: DWARF Location Expressions

Common opcodes in location expressions:

| Opcode | Hex | Name | Use |
|--------|-----|------|-----|
| `DW_OP_plus_uconst` | 0x23 | 35 | Add unsigned constant → Used in PS3 for member offsets |
| `DW_OP_deref` | 0x06 | 6 | Dereference → Used for indirect addressing |
| `DW_OP_const1u` | 0x08 | 8 | 1-byte unsigned constant |
| `DW_OP_const4s` | 0x0c | 12 | 4-byte signed constant |

Most PS3 member locations appear to be:
- `[35, offset]` → Simple offset via `DW_OP_plus_uconst`

## Files to Modify

1. **Create new utility module:**
   - `src/ddon_dwarf_reconstructor/generators/utils/dwarf_location_parser.py`
   - Function: `parse_location_offset(attr_value) -> int | None`

2. **Modify ClassParser:**
   - `src/ddon_dwarf_reconstructor/generators/utils/class_parser.py`
   - Import and use `parse_location_offset()`

3. **Add Tests:**
   - `tests/generators/utils/test_dwarf_location_parser.py`
   - Test cases for:
     - PS4 style: integer offset
     - PS3 style: `[35, offset]` location expression
     - Edge cases: empty expressions, unknown opcodes

## Testing Evidence

### PS3 MtDTI Members with Location Expressions

```
Member: _vptr$
  Offset value: [35, 0]  <-- Opcode 35, offset 0

Member: mName  
  Offset value: [35, 4]  <-- Opcode 35, offset 4

Member: mpNext
  Offset value: [35, 8]  <-- Opcode 35, offset 8

Member: mpChild
  Offset value: [35, 12] <-- Opcode 35, offset 12
```

All PS3 members tested use the same pattern: `[35, actual_offset]`

## Next Steps

1. Create `dwarf_location_parser.py` with `parse_location_offset()` function
2. Add unit tests for location expression parsing
3. Modify `class_parser.py` to use the new parser
4. Test with PS3 EBOOT.ELF (MtDTI class)
5. Verify PS4 still works (regression test)
6. Run full test suite

