// Reduced declaration schedule, with host-size checks only.
struct MtArray {
    unsigned char bytes[32];
};

template <typename Node> class cNodeParam;

template <typename Node> class cTree {
public:
    class cNode {
    public:
        virtual ~cNode();
        cNodeParam<Node>* mpParam;
        cNode* mpRight;
        cNode* mpLeft;
        template <typename T> void searchT(T&);
    };

    virtual ~cTree();
    unsigned int mParamNum;
    cNode* mpRoot;
    MtArray mParams;
    template <typename T> void searchT(T&);
};

struct rGrass {
    struct cCluster {};
    cTree<cCluster> mCluster;
};

struct uGrass {
    template <typename Node> class cRenderOperatorCDRAW;
    void draw(cRenderOperatorCDRAW<rGrass::cCluster>&);
};

namespace nDDOUtility {
template <typename T, unsigned int N> struct cArray {
    T elems[N];
};
}

struct cPawnActInterDisableMgr {
    struct cNode {
        unsigned char payload[32];
    };
    using cNodes = nDDOUtility::cArray<cNode, 16>;
    cNodes mNodes;
};

static_assert(sizeof(cTree<rGrass::cCluster>) == 56);
static_assert(sizeof(cTree<rGrass::cCluster>::cNode) == 32);
static_assert(sizeof(cPawnActInterDisableMgr::cNodes) == 512);
