# Feature
- A special simplified, C-like struct-only output mode

# Feature
- A special output to optimize Ghidra structures: identify alignment and packing hints per structure (CSV-like: struct class, packing)

# TODO:
Here are bugs and improvements I would like you to work on ultrathink
Tell me if you need me to clarify something, but otherwise look into the README and docs folder ultrathink
Analyze source code and create a detailed plan and track the todos before you begin ultrathink


    # Bug
    The forward declarations need to be recursively traced and dumped, this can easily be verified with MtObject already that his feature is missing currently.

    # Improvement
    Only save the cache when it has actually changed compared to disk to save up on I/O

    # Bug
    There are type definitions that do not resolve, check rGUI

    # Bug
    There are some unhandled tags in different handlers. The most recent log is quite large and has a lot of information inside of it as it is now running a full dump on almost 300 symbols. Please analyze these issues.

    * The type_chain_traverser runs into the following unhandled tags:
    DW_TAG_class_type
    DW_TAG_ptr_to_member_type
    DW_TAG_structure_type
    DW_TAG_subroutine_type
    DW_TAG_union_type

    * The class_parser runs into the following unhandled tags:
    DW_TAG_template_type_param
    DW_TAG_template_value_param



# Q/A

    1. It's in the logs folder, but it's rather large, you will have to use grepping tools: logs\ddon_reconstructor_20251011_222538.log.

    The information which specific tags are causing warnings can be found via "unhandled" as a keyword.

    In rGUI there is a typedef like "typedef InputLayouts HInputLayout;" where "InputLayouts is not defined.
    In IDA Pro it generates this:
    ```
    typedef nDraw::InputLayouts *nDraw::HInputLayout;

    struct nDraw::InputLayouts
    {
    u32 num;
    nDraw::Layout *layouts;
    };
    ```

    Also the typedef "typedef PixelShaderObject HPixelShader;" seems strange. This is what IDA Pro outputs:
    ```
    typedef nPS4::PixelShaderObject *nDraw::HPixelShader;

    struct __cppobj nPS4::PixelShaderObject : nPS4::ShaderObject
    {
    sce::Gnmx::PsShader *mpPs;
    sce::Gnmx::InputResourceOffsets mInputResourceOffsets;
    };
    ```
    Also some of these void typedefs like "typedef void HVertexBuffer;" look like this in IDA Pro:
    ```
    typedef void *nDraw::HVertexBuffer;
    ```

    2. Recursion depth 5 should be good.

    3. Go for it.

    4. Please implement templates properly.

    NEW: I have added the DWARF4.txt specification - you can reference the samples in there to get a better understanding of various tag handling problems.