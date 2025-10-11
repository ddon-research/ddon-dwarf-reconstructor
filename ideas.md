# Feature
- A special simplified, C-like struct-only output mode

# Feature
- A special output to optimize Ghidra structures: identify alignment and packing hints per structure (CSV-like: struct class, packing)

# Feature
- Add namespace information to types, enums, classes etc.

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