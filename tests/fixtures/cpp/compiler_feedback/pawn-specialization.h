#pragma once
namespace nDDOUtility { template <typename Node, unsigned int Count> class cArray; }
class cPawnActInterDisableMgr;
template <> class nDDOUtility::cArray<cPawnActInterDisableMgr::cNode, 16> {
public:
    cPawnActInterDisableMgr::cNode elems[16];
};
