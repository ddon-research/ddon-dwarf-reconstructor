#pragma once
namespace nDDOUtility { template <typename Node, unsigned int Count> class cArray; }
class cPawnActInterDisableMgr {
public:
    class cNode {};
    using cNodes = nDDOUtility::cArray<cNode, 16>;
    cNodes mNodes;
};
