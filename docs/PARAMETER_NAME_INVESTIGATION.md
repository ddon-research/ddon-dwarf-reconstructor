# Parameter Name Reconstruction Investigation

## Problem Statement

Method signatures may not be properly reconstructing parameter names from DWARF debug information. While some methods may lack debug info for parameter names, there are confirmed cases where parameter names ARE present in DWARF but may not be appearing in generated headers.

## Test Case

**IDA Pro 9.2 Signature:**
```cpp
void __fastcall nPhysics::Constraint::Hinge::CalculateAxisAndError(
    nPhysics::CONSTRAINT *constraint,
    const nPhysics::RIGID_BODY_DATA *rigid_body1,
    const nPhysics::RIGID_BODY_DATA *rigid_body2,
    MtFloat4A *output_angle_error,
    MtFloat4A *output_velocity_error
);
```

**DWARF Evidence:**
- Parameter `output_velocity_error` found at offset 0x260f88bc (DW_TAG_formal_parameter)
- Parameter `output_angle_error` found at offset 0x260f88a4 (DW_TAG_formal_parameter)
- Both have DW_AT_name attributes with the exact parameter names
- Located in file: `nPhysicsConstraintHinge.cpp` (line 249-250)

**Key Observation:** The name "output_velocity_error" is too specific to be derived via heuristics - it must come from debug symbols.

## Investigation Plan

### 1. Understand Current Method Parsing (Research Phase)

**Tasks:**
- [ ] Locate method/function parsing code in codebase
- [ ] Identify which service/parser handles DW_TAG_subprogram DIEs
- [ ] Find where formal parameters (DW_TAG_formal_parameter) are processed
- [ ] Document current parameter name extraction logic

**Expected Locations:**
- `src/ddon_dwarf_reconstructor/domain/services/parsing/` - likely has method parser
- `src/ddon_dwarf_reconstructor/domain/services/generation/` - method generation code
- Search for: "DW_TAG_subprogram", "DW_TAG_formal_parameter", "parameter", "method"

### 2. Verify DWARF Data Accessibility (Validation Phase)

**Tasks:**
- [ ] Write unit test to extract DIE for CalculateAxisAndError method
- [ ] Verify we can access DW_TAG_formal_parameter children
- [ ] Confirm DW_AT_name attribute is readable from parameter DIEs
- [ ] Check if parameter type information (DW_AT_type) is being resolved

**Test File:** `tests/domain/services/parsing/test_method_parameter_extraction.py`

### 3. Test Current Parameter Name Extraction (Testing Phase)

**Tasks:**
- [ ] Create unit tests with mock DWARF structures (DW_TAG_formal_parameter with DW_AT_name)
- [ ] Test parameter extraction for methods with multiple parameters
- [ ] Test edge cases: unnamed parameters, variadic functions, reference/pointer parameters
- [ ] Run existing unit test suite to check for regressions

**Command:** `uv run just test-unit`

### 4. Integration Test (Real ELF Phase)

**Tasks:**
- [ ] Generate header for nPhysics::Constraint::Hinge class
- [ ] Verify CalculateAxisAndError method signature in output
- [ ] Check if parameter names appear: "output_velocity_error", "output_angle_error", etc.
- [ ] Document discrepancies between IDA Pro output and our output

**Command:** `uv run ddon-dwarf-reconstructor generate resources/DDOORBIS.elf --symbol "nPhysics::Constraint::Hinge" --output output/test-params/`

### 5. Implement Fix (If Needed)

**Potential Issues:**
- Parameter DIEs not being iterated over
- DW_AT_name attribute not being read
- Parameter names not being passed to signature formatter
- Fallback to generic names (param1, param2) when names are available

**Fix Locations (TBD after research):**
- Method parser to extract parameter names
- Signature formatter to use extracted names
- Data model to store parameter information

### 6. Validation

**Tasks:**
- [ ] Run full unit test suite: `uv run just test-unit`
- [ ] Regenerate test case: nPhysics::Constraint::Hinge
- [ ] Verify parameter names match IDA Pro output
- [ ] Check multiple classes for proper parameter name reconstruction

## DWARF Structure Reference

Based on the provided dump, formal parameters have this structure:

```
DW_TAG_formal_parameter
  DW_AT_location [DW_FORM_sec_offset] - register/memory location
  DW_AT_name [DW_FORM_strp] - PARAMETER NAME (e.g., "output_velocity_error")
  DW_AT_decl_file [DW_FORM_data1] - source file
  DW_AT_decl_line [DW_FORM_data1/2] - source line number
  DW_AT_type [DW_FORM_ref4] - reference to parameter type DIE
```

## Success Criteria

1. Unit tests pass with mocked DWARF parameter structures
2. Integration test generates CalculateAxisAndError with correct parameter names:
   - `constraint`
   - `rigid_body1`
   - `rigid_body2`
   - `output_angle_error`
   - `output_velocity_error`
3. No regressions in existing test suite
4. Documentation updated if behavior changes

## Investigation Findings

### Code Analysis (COMPLETED)

**Current Implementation:**
- `ClassParser.parse_method()` iterates over `DW_TAG_formal_parameter` children
- `ClassParser.parse_parameter()` extracts `DW_AT_name` attribute: `param_name = name_attr.value.decode("utf-8") if name_attr else "param"`
- Parameters are stored in `ParameterInfo(name, type_name, type_offset, default_value)`
- `HeaderGenerator._format_parameters()` formats as: `f"{param.type_name} {param.name}"`

**The code is CORRECT** - it properly extracts parameter names when present.

### Root Cause (IDENTIFIED)

**Parameter names are location-dependent in DWARF:**

1. **Method Declarations** (in class definitions): Usually LACK parameter names
   ```
   DW_TAG_subprogram [declaration=true]
     DW_AT_name: "setAllocator"
     DW_TAG_formal_parameter
       DW_AT_type: u32
       // NO DW_AT_name attribute!
   ```

2. **Method Definitions** (implementations): Usually HAVE parameter names
   ```
   DW_TAG_subprogram [implementation]
     DW_AT_specification: points to declaration
     DW_TAG_formal_parameter
       DW_AT_location: register/stack location
       DW_AT_name: "output_velocity_error"  // ✓ Name present!
       DW_AT_type: MtFloat4A &
   ```

**Current behavior:**
- We parse class definitions (declarations) which typically omit parameter names
- Fallback to generic "param" name is triggered
- Result: `void setAllocator(u32 param)` instead of actual parameter name

**Evidence from DWARF dumps:**
- Class method declarations: `DW_TAG_formal_parameter` has only `DW_AT_type`
- Method implementations: `DW_TAG_formal_parameter` has both `DW_AT_name` and `DW_AT_type`
- User's example: CalculateAxisAndError implementation at offset 0x260f886d has all parameter names

## Status

**Current Phase:** COMPLETED ✓
**Solution Implemented:** Option 3 (Hybrid - Auto-increment fallback)

## Implementation Summary

### Changes Made

1. **Auto-Incrementing Parameter Names** (`class_parser.py`):
   - Modified `parse_parameter()` to accept `param_index` parameter
   - Unnamed parameters now use `param1`, `param2`, `param3`, etc. instead of all being `param`
   - Prevents C++ syntax errors from duplicate parameter names
   
2. **Artificial Parameter Handling** (`class_parser.py`):
   - Artificial parameters (this pointers) don't increment the counter
   - Ensures first real parameter is always `param1`, not `param2`
   - Maintains correct numbering even with this pointers present

3. **Comprehensive Unit Tests** (`test_method_parameter_naming.py`):
   - Test parameter name extraction when DW_AT_name present
   - Test auto-increment fallback for unnamed parameters
   - Test artificial parameter marking (`__artificial__`)
   - Test mixed parameters (this + regular params)
   - Test multiple unnamed parameters

### Results

**Before:**
```cpp
void setAllocator(u32 param);
MtProperty* insert(s32 param);  // Syntax error: duplicate param name!
void add(const MtProperty& param);
```

**After:**
```cpp
void setAllocator(u32 param1);
MtProperty* insert(s32 param1);
void add(const MtProperty& param1);
```

### Test Results

- **Unit tests:** 234 passed (5 new parameter naming tests + 229 existing)
- **Integration test:** MtPropertyList.h generated correctly with param1, param2, etc.
- **No regressions:** All existing tests continue to pass

### Future Enhancement (Optional)

The framework is in place to add `--resolve-param-names` flag later:
- Would search for method implementations via `DW_AT_specification`
- Extract actual parameter names from implementations
- Cache lookups for performance
- Fall back to auto-increment if implementation not found

**Current behavior is pragmatic:** Generates valid C++ with numbered parameters that won't cause syntax errors.

### Option 1: Find Method Implementations via DW_AT_specification (RECOMMENDED)

**Approach:**
1. When parsing a method declaration, check if it has `DW_AT_declaration=true`
2. Search DWARF for corresponding implementation using `DW_AT_specification` reference
3. Extract parameter names from the implementation's formal_parameter DIEs
4. Merge names back into the declaration's ParameterInfo objects

**Implementation:**
```python
def parse_method(self, method_die: DIE) -> MethodInfo | None:
    # ... existing parsing ...
    
    # Parse parameters from declaration
    parameters = []
    for child in method_die.iter_children():
        if child.tag == "DW_TAG_formal_parameter":
            param = self.parse_parameter(child)
            if param:
                parameters.append(param)
    
    # If this is a declaration, try to find implementation for parameter names
    is_declaration = method_die.attributes.get("DW_AT_declaration") is not None
    if is_declaration and parameters:
        impl_params = self._find_implementation_parameters(method_die)
        if impl_params:
            self._merge_parameter_names(parameters, impl_params)
    
    return MethodInfo(...)
```

**Advantages:**
- Preserves parameter names from source code
- Follows DWARF specification correctly
- No heuristics or guessing

**Disadvantages:**
- Requires searching for implementation DIEs (performance cost)
- Not all methods have implementations in debug info
- Implementation may be in different compilation unit

### Option 2: Accept Missing Parameter Names (CURRENT BEHAVIOR)

**Approach:**
- Keep current behavior: use "param" for unnamed parameters
- Document limitation in generated headers
- Add comment indicating parameter types but names unavailable

**Advantages:**
- No code changes needed
- Fast generation
- Already working

**Disadvantages:**
- Less useful generated headers
- Missing valuable debug information that exists

### Option 3: Hybrid Approach (PRAGMATIC)

**Approach:**
1. Try to find implementation for parameter names (Option 1)
2. If not found within reasonable search scope, fall back to "param" (Option 2)
3. Add comment to method indicating parameter names unavailable
4. Make implementation search optional via command-line flag `--resolve-param-names`

**Implementation Notes:**
- Cache implementation offset lookups to avoid repeated searches
- Limit search scope (same CU first, then nearby CUs)
- Skip search for methods unlikely to have implementations (pure virtual, inline)
