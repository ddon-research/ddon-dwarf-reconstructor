# DWARF 2/3/4 Semantic Index

> Schema: `1`; parser: `0.1.0`

## Version inventory

| Version | Tags | Attributes | Forms | Operations | Languages |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 2 | 54 | 67 | 21 | 71 | 13 |
| 3 | 61 | 92 | 23 | 76 | 22 |
| 4 | 63 | 98 | 28 | 85 | 23 |

## High-risk relationship checks

### DWARF 2
- `DW_AT_containing_type` applies to `DW_TAG_ptr_to_member_type`: `True`.
- `DW_AT_containing_type` applies to `DW_TAG_class_type`: `False`.
- `DW_AT_high_pc` classes: `address`.

### DWARF 3
- `DW_AT_containing_type` applies to `DW_TAG_ptr_to_member_type`: `True`.
- `DW_AT_containing_type` applies to `DW_TAG_class_type`: `False`.
- `DW_AT_high_pc` classes: `address`.

### DWARF 4
- `DW_AT_containing_type` applies to `DW_TAG_ptr_to_member_type`: `True`.
- `DW_AT_containing_type` applies to `DW_TAG_class_type`: `False`.
- `DW_AT_high_pc` classes: `address, constant`.

## Attribute encodings

### DWARF 2

| Attribute | Value | Classes |
| --- | ---: | --- |
| `DW_AT_abstract_origin` | `0x31` | reference |
| `DW_AT_accessibility` | `0x32` | constant |
| `DW_AT_address_class` | `0x33` | constant |
| `DW_AT_artificial` | `0x34` | flag |
| `DW_AT_base_types` | `0x35` | reference |
| `DW_AT_bit_offset` | `0x0c` | constant |
| `DW_AT_bit_size` | `0x0d` | constant |
| `DW_AT_byte_size` | `0x0b` | constant |
| `DW_AT_calling_convention` | `0x36` | constant |
| `DW_AT_common_reference` | `0x1a` | reference |
| `DW_AT_comp_dir` | `0x1b` | string |
| `DW_AT_const_value` | `0x1c` | block, constant, string |
| `DW_AT_containing_type` | `0x1d` | reference |
| `DW_AT_count` | `0x37` | constant, reference |
| `DW_AT_data_member_location` | `0x38` | block, reference |
| `DW_AT_decl_column` | `0x39` | constant |
| `DW_AT_decl_file` | `0x3a` | constant |
| `DW_AT_decl_line` | `0x3b` | constant |
| `DW_AT_declaration` | `0x3c` | flag |
| `DW_AT_default_value` | `0x1e` | reference |
| `DW_AT_discr` | `0x15` | reference |
| `DW_AT_discr_list` | `0x3d` | block |
| `DW_AT_discr_value` | `0x16` | constant |
| `DW_AT_encoding` | `0x3e` | constant |
| `DW_AT_external` | `0x3f` | flag |
| `DW_AT_frame_base` | `0x40` | block, constant |
| `DW_AT_friend` | `0x41` | reference |
| `DW_AT_hi_user` | `0x3fff` |  |
| `DW_AT_high_pc` | `0x12` | address |
| `DW_AT_identifier_case` | `0x42` | constant |
| `DW_AT_import` | `0x18` | reference |
| `DW_AT_inline` | `0x20` | constant |
| `DW_AT_is_optional` | `0x21` | flag |
| `DW_AT_language` | `0x13` | constant |
| `DW_AT_lo_user` | `0x2000` |  |
| `DW_AT_location` | `0x02` | block, constant |
| `DW_AT_low_pc` | `0x11` | address |
| `DW_AT_lower_bound` | `0x22` | constant, reference |
| `DW_AT_macro_info` | `0x43` | constant |
| `DW_AT_name` | `0x03` | string |
| `DW_AT_namelist_item` | `0x44` | block |
| `DW_AT_ordering` | `0x09` | constant |
| `DW_AT_priority` | `0x45` | reference |
| `DW_AT_producer` | `0x25` | string |
| `DW_AT_prototyped` | `0x27` | flag |
| `DW_AT_return_addr` | `0x2a` | block, constant |
| `DW_AT_segment` | `0x46` | block, constant |
| `DW_AT_sibling` | `0x01` | reference |
| `DW_AT_specification` | `0x47` | reference |
| `DW_AT_start_scope` | `0x2c` | constant |
| `DW_AT_static_link` | `0x48` | block, constant |
| `DW_AT_stmt_list` | `0x10` | constant |
| `DW_AT_stride_size` | `0x2e` | constant |
| `DW_AT_string_length` | `0x19` | block, constant |
| `DW_AT_type` | `0x49` | reference |
| `DW_AT_upper_bound` | `0x2f` | constant, reference |
| `DW_AT_use_location` | `0x4a` | block, constant |
| `DW_AT_variable_parameter` | `0x4b` | flag |
| `DW_AT_virtuality` | `0x4c` | constant |
| `DW_AT_visibility` | `0x17` | constant |
| `DW_AT_vtable_elem_location` | `0x4d` | block, reference |

### DWARF 3

| Attribute | Value | Classes |
| --- | ---: | --- |
| `DW_AT_abstract_origin` | `0x31` | reference |
| `DW_AT_accessibility` | `0x32` | constant |
| `DW_AT_address_class` | `0x33` | constant |
| `DW_AT_allocated ‡` | `0x4e` | block, constant, reference |
| `DW_AT_artificial` | `0x34` | flag |
| `DW_AT_associated ‡` | `0x4f` | block, constant, reference |
| `DW_AT_base_types` | `0x35` | reference |
| `DW_AT_binary_scale ‡` | `0x5b` | constant |
| `DW_AT_bit_offset` | `0x0c` | block, constant, reference |
| `DW_AT_bit_size` | `0x0d` | block, constant, reference |
| `DW_AT_bit_stride` | `0x2e` | constant |
| `DW_AT_byte_size` | `0x0b` | block, constant, reference |
| `DW_AT_byte_stride ‡` | `0x51` | block, constant, reference |
| `DW_AT_call_column ‡` | `0x57` | constant |
| `DW_AT_call_file ‡` | `0x58` | constant |
| `DW_AT_call_line ‡` | `0x59` | constant |
| `DW_AT_calling_convention` | `0x36` | constant |
| `DW_AT_common_reference` | `0x1a` | reference |
| `DW_AT_comp_dir` | `0x1b` | string |
| `DW_AT_const_value` | `0x1c` | block, constant, string |
| `DW_AT_containing_type` | `0x1d` | reference |
| `DW_AT_count` | `0x37` | block, constant, reference |
| `DW_AT_data_location ‡` | `0x50` | block |
| `DW_AT_data_member_location` | `0x38` | block, constant, loclistptr |
| `DW_AT_decimal_scale ‡` | `0x5c` | constant |
| `DW_AT_decimal_sign ‡` | `0x5e` | constant |
| `DW_AT_decl_column` | `0x39` | constant |
| `DW_AT_decl_file` | `0x3a` | constant |
| `DW_AT_decl_line` | `0x3b` | constant |
| `DW_AT_declaration` | `0x3c` | flag |
| `DW_AT_default_value` | `0x1e` | reference |
| `DW_AT_description ‡` | `0x5a` | string |
| `DW_AT_digit_count ‡` | `0x5f` | constant |
| `DW_AT_discr` | `0x15` | reference |
| `DW_AT_discr_list` | `0x3d` | block |
| `DW_AT_discr_value` | `0x16` | constant |
| `DW_AT_elemental ‡` | `0x66` | flag |
| `DW_AT_encoding` | `0x3e` | constant |
| `DW_AT_endianity ‡` | `0x65` | constant |
| `DW_AT_entry_pc ‡` | `0x52` | address |
| `DW_AT_explicit ‡` | `0x63` | flag |
| `DW_AT_extension ‡` | `0x54` | reference |
| `DW_AT_external` | `0x3f` | flag |
| `DW_AT_frame_base` | `0x40` | block, loclistptr |
| `DW_AT_friend` | `0x41` | reference |
| `DW_AT_hi_user` | `0x3fff` |  |
| `DW_AT_high_pc` | `0x12` | address |
| `DW_AT_identifier_case` | `0x42` | constant |
| `DW_AT_import` | `0x18` | reference |
| `DW_AT_inline` | `0x20` | constant |
| `DW_AT_is_optional` | `0x21` | flag |
| `DW_AT_language` | `0x13` | constant |
| `DW_AT_lo_user` | `0x2000` |  |
| `DW_AT_location` | `0x02` | block, loclistptr |
| `DW_AT_low_pc` | `0x11` | address |
| `DW_AT_lower_bound` | `0x22` | block, constant, reference |
| `DW_AT_macro_info` | `0x43` | macptr |
| `DW_AT_mutable ‡` | `0x61` | flag |
| `DW_AT_name` | `0x03` | string |
| `DW_AT_namelist_item` | `0x44` | block |
| `DW_AT_object_pointer ‡` | `0x64` | reference |
| `DW_AT_ordering` | `0x09` | constant |
| `DW_AT_picture_string ‡` | `0x60` | string |
| `DW_AT_priority` | `0x45` | reference |
| `DW_AT_producer` | `0x25` | string |
| `DW_AT_prototyped` | `0x27` | flag |
| `DW_AT_pure ‡` | `0x67` | flag |
| `DW_AT_ranges ‡` | `0x55` | rangelistptr |
| `DW_AT_recursive ‡` | `0x68` | flag |
| `DW_AT_return_addr` | `0x2a` | block, loclistptr |
| `DW_AT_segment` | `0x46` | block, loclistptr |
| `DW_AT_sibling` | `0x01` | reference |
| `DW_AT_small ‡` | `0x5d` | reference |
| `DW_AT_specification` | `0x47` | reference |
| `DW_AT_start_scope` | `0x2c` | constant |
| `DW_AT_static_link` | `0x48` | block, loclistptr |
| `DW_AT_stmt_list` | `0x10` | lineptr |
| `DW_AT_string_length` | `0x19` | block, loclistptr |
| `DW_AT_threads_scaled ‡` | `0x62` | flag |
| `DW_AT_trampoline ‡` | `0x56` | address, flag, reference, string |
| `DW_AT_type` | `0x49` | reference |
| `DW_AT_upper_bound` | `0x2f` | block, constant, reference |
| `DW_AT_use_UTF8 ‡` | `0x53` | flag |
| `DW_AT_use_location` | `0x4a` | block, loclistptr |
| `DW_AT_variable_parameter` | `0x4b` | flag |
| `DW_AT_virtuality` | `0x4c` | constant |
| `DW_AT_visibility` | `0x17` | constant |
| `DW_AT_vtable_elem_location` | `0x4d` | block, loclistptr |

### DWARF 4

| Attribute | Value | Classes |
| --- | ---: | --- |
| `DW_AT_abstract_origin` | `0x31` | reference |
| `DW_AT_accessibility` | `0x32` | constant |
| `DW_AT_address_class` | `0x33` | constant |
| `DW_AT_allocated` | `0x4e` | constant, exprloc, reference |
| `DW_AT_artificial` | `0x34` | flag |
| `DW_AT_associated` | `0x4f` | constant, exprloc, reference |
| `DW_AT_base_types` | `0x35` | reference |
| `DW_AT_binary_scale` | `0x5b` | constant |
| `DW_AT_bit_offset` | `0x0c` | constant, exprloc, reference |
| `DW_AT_bit_size` | `0x0d` | constant, exprloc, reference |
| `DW_AT_bit_stride` | `0x2e` | constant, exprloc, reference |
| `DW_AT_byte_size` | `0x0b` | constant, exprloc, reference |
| `DW_AT_byte_stride` | `0x51` | constant, exprloc, reference |
| `DW_AT_call_column` | `0x57` | constant |
| `DW_AT_call_file` | `0x58` | constant |
| `DW_AT_call_line` | `0x59` | constant |
| `DW_AT_calling_convention` | `0x36` | constant |
| `DW_AT_common_reference` | `0x1a` | reference |
| `DW_AT_comp_dir` | `0x1b` | string |
| `DW_AT_const_expr ‡` | `0x6c` | flag |
| `DW_AT_const_value` | `0x1c` | block, constant, string |
| `DW_AT_containing_type` | `0x1d` | reference |
| `DW_AT_count` | `0x37` | constant, exprloc, reference |
| `DW_AT_data_bit_offset ‡` | `0x6b` | constant |
| `DW_AT_data_location` | `0x50` | exprloc |
| `DW_AT_data_member_location` | `0x38` | constant, exprloc, loclistptr |
| `DW_AT_decimal_scale` | `0x5c` | constant |
| `DW_AT_decimal_sign` | `0x5e` | constant |
| `DW_AT_decl_column` | `0x39` | constant |
| `DW_AT_decl_file` | `0x3a` | constant |
| `DW_AT_decl_line` | `0x3b` | constant |
| `DW_AT_declaration` | `0x3c` | flag |
| `DW_AT_default_value` | `0x1e` | reference |
| `DW_AT_description` | `0x5a` | string |
| `DW_AT_digit_count` | `0x5f` | constant |
| `DW_AT_discr` | `0x15` | reference |
| `DW_AT_discr_list` | `0x3d` | block |
| `DW_AT_discr_value` | `0x16` | constant |
| `DW_AT_elemental` | `0x66` | flag |
| `DW_AT_encoding` | `0x3e` | constant |
| `DW_AT_endianity` | `0x65` | constant |
| `DW_AT_entry_pc` | `0x52` | address |
| `DW_AT_enum_class ‡` | `0x6d` | flag |
| `DW_AT_explicit` | `0x63` | flag |
| `DW_AT_extension` | `0x54` | reference |
| `DW_AT_external` | `0x3f` | flag |
| `DW_AT_frame_base` | `0x40` | exprloc, loclistptr |
| `DW_AT_friend` | `0x41` | reference |
| `DW_AT_hi_user` | `0x3fff` |  |
| `DW_AT_high_pc` | `0x12` | address, constant |
| `DW_AT_identifier_case` | `0x42` | constant |
| `DW_AT_import` | `0x18` | reference |
| `DW_AT_inline` | `0x20` | constant |
| `DW_AT_is_optional` | `0x21` | flag |
| `DW_AT_language` | `0x13` | constant |
| `DW_AT_linkage_name ‡` | `0x6e` | string |
| `DW_AT_lo_user` | `0x2000` |  |
| `DW_AT_location` | `0x02` | exprloc, loclistptr |
| `DW_AT_low_pc` | `0x11` | address |
| `DW_AT_lower_bound` | `0x22` | constant, exprloc, reference |
| `DW_AT_macro_info` | `0x43` | macptr |
| `DW_AT_main_subprogram ‡` | `0x6a` | flag |
| `DW_AT_mutable` | `0x61` | flag |
| `DW_AT_name` | `0x03` | string |
| `DW_AT_namelist_item` | `0x44` | reference |
| `DW_AT_object_pointer` | `0x64` | reference |
| `DW_AT_ordering` | `0x09` | constant |
| `DW_AT_picture_string` | `0x60` | string |
| `DW_AT_priority` | `0x45` | reference |
| `DW_AT_producer` | `0x25` | string |
| `DW_AT_prototyped` | `0x27` | flag |
| `DW_AT_pure` | `0x67` | flag |
| `DW_AT_ranges` | `0x55` | rangelistptr |
| `DW_AT_recursive` | `0x68` | flag |
| `DW_AT_return_addr` | `0x2a` | exprloc, loclistptr |
| `DW_AT_segment` | `0x46` | exprloc, loclistptr |
| `DW_AT_sibling` | `0x01` | reference |
| `DW_AT_signature ‡` | `0x69` | reference |
| `DW_AT_small` | `0x5d` | reference |
| `DW_AT_specification` | `0x47` | reference |
| `DW_AT_start_scope` | `0x2c` | rangelistptr |
| `DW_AT_static_link` | `0x48` | exprloc, loclistptr |
| `DW_AT_stmt_list` | `0x10` | lineptr |
| `DW_AT_string_length` | `0x19` | exprloc, loclistptr |
| `DW_AT_threads_scaled` | `0x62` | flag |
| `DW_AT_trampoline` | `0x56` | address, flag, reference, string |
| `DW_AT_type` | `0x49` | reference |
| `DW_AT_upper_bound` | `0x2f` | constant, exprloc, reference |
| `DW_AT_use_UTF8` | `0x53` | flag |
| `DW_AT_use_location` | `0x4a` | exprloc, loclistptr |
| `DW_AT_variable_parameter` | `0x4b` | flag |
| `DW_AT_virtuality` | `0x4c` | constant |
| `DW_AT_visibility` | `0x17` | constant |
| `DW_AT_vtable_elem_location` | `0x4d` | exprloc, loclistptr |
