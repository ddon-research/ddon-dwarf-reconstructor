# Feature
- A special simplified, C-like struct-only output mode

# Feature
- A special output to optimize Ghidra structures: identify alignment and packing hints per structure (CSV-like: struct class, packing)

# Feature
- Add namespace information to types, enums, classes etc.

# Enhancement: Cache Metadata for Complete Definition Detection

## Problem
Currently, the persistent symbol cache stores only symbol name → DIE offset mappings. When the cache is loaded, validation must occur at retrieval time to check if the cached offset points to a complete class definition or just a forward declaration. This validation requires loading the DIE and checking the `DW_AT_declaration` attribute, which adds overhead.

## Proposed Solution
Enhance cache entries to store completeness metadata alongside offsets:

```python
{
    "symbol_name": {
        "offset": 0x12345,
        "cu_offset": 0x100,
        "is_complete": true,          # New: not a forward declaration
        "has_children": true,          # New: has members/methods
        "byte_size": 128,              # New: size in bytes
        "completeness_score": 10128    # New: pre-calculated score
    }
}
```

## Benefits
1. **Skip validation overhead**: Cache hit can immediately determine if entry is usable
2. **Faster filtering**: Can reject incomplete definitions without loading DIE
3. **Better cache utilization**: Know quality of cached entries
4. **Pre-computed scoring**: No need to recalculate completeness score

## Trade-offs
1. **Larger cache files**: More metadata per entry (~16-24 extra bytes)
2. **Cache invalidation complexity**: Need to update cache when parsing logic changes
3. **Migration overhead**: Existing caches need conversion or rebuild

## Current Implementation (Validation-on-Retrieval)
The current approach keeps cache entries simple and performs validation when retrieving:
- **Pros**: Simple cache format, no migration needed, always uses latest validation logic
- **Cons**: Validation overhead on every cache hit, potential wasted lookups

## Recommendation
Keep validation-on-retrieval approach for now due to:
1. Cache rebuild is already expensive (full ELF scan), validation overhead is marginal
2. Simpler cache format reduces bugs and maintenance
3. Validation logic may evolve as DWARF edge cases are discovered
4. Current performance is acceptable for MTFramework use case

Consider metadata enhancement if:
- Cache validation becomes a measurable bottleneck (profile first)
- Multiple cache hits per symbol lookup become common
- Cache format stabilizes (no breaking changes for 6+ months)

## Implementation Notes
If implementing metadata enhancement:
1. Add versioning to cache format for migration detection
2. Include timestamp or ELF hash for cache invalidation
3. Store DWARF version used during cache build
4. Provide tool to inspect and validate cache contents
5. Document cache format in ARCHITECTURE.md

# Bug
- rAbilityAddData is not found/understood, it is part of a namespace and generates an empty file

# Bug
- rStageList, rStageAdjoinList, rStaminaDecTbl, rStartPosArea is unexpectedly empty
For example, according to IDA Pro it should roughly look like this:
```
struct __cppobj __attribute__((aligned(8))) rStageAdjoinList : cResource
{
  rStageAdjoinList::AdjoinInfoArray mAdjoinInfo;
  rStageAdjoinList::JumpPositionArray mJumpPosition;
  u16 mStageNo;
};
```

# Bug
- Array types are still generated with the wrong declaration syntax
```
class STRING
{
public:
    s32 ref;  // offset: 0x0
    u32 length;  // offset: 0x4
    u8[] str;  // offset: 0x8
};
```

# Bug
- When a function has multiple "formal parameters", avoid generating the name "param", as that just leads to syntax errors and method signatures in declarations do not need any parameter names and we don't have access to them anyway => Question is how does IDA recover parameter names? e.g. "bool __fastcall cResource::convertEx(cResource *this, MtStream *, cResource::CONVERT_TYPE type);"
- Reconstructing / providing vtable information via "DW_AT_vtable_elem_location" e.g. in 
```
0x0001326c:     DW_TAG_subprogram [55] * (0x00012e3f)
                  DW_AT_name [DW_FORM_strp]     ( .debug_str[0x00006899] = "convertEx")
                  DW_AT_decl_file [DW_FORM_data1]       ("D:\publishDDO_PS4_02_02_Master\DDO_02_02\DD_ONLINE/..\capdev200\XFramework/cResource.h")
                  DW_AT_decl_line [DW_FORM_data1]       (239)
                  DW_AT_type [DW_FORM_ref4]     (cu + 0x12f2 => {0x00001f8f} "bool")
                  DW_AT_virtuality [DW_FORM_data1]      (DW_VIRTUALITY_virtual)
                  DW_AT_vtable_elem_location [DW_FORM_exprloc]  (DW_OP_constu 0xe)
                  DW_AT_declaration [DW_FORM_flag_present]      (true)
                  DW_AT_external [DW_FORM_flag_present] (true)
                  DW_AT_accessibility [DW_FORM_data1]   (DW_ACCESS_protected)
                  DW_AT_containing_type [DW_FORM_ref4]  (cu + 0x121a2 => {0x00012e3f} "cResource")

0x00013280:       DW_TAG_formal_parameter [6]   (0x0001326c)
                    DW_AT_type [DW_FORM_ref4]   (cu + 0x1273b => {0x000133d8} "cResource *")
                    DW_AT_artificial [DW_FORM_flag_present]     (true)

0x00013285:       DW_TAG_formal_parameter [15]   (0x0001326c)
                    DW_AT_type [DW_FORM_ref4]   (cu + 0x12740 => {0x000133dd} "MtStream &")

0x0001328a:       DW_TAG_formal_parameter [15]   (0x0001326c)
                    DW_AT_type [DW_FORM_ref4]   (cu + 0x125f3 => {0x00013290} "cResource::CONVERT_TYPE")

0x0001328f:       NULL

```