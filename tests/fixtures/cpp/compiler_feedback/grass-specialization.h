#pragma once
template <typename Node> class cTree;
class rGrass;
template <> class cTree<rGrass::cCluster> { public: int value; };
