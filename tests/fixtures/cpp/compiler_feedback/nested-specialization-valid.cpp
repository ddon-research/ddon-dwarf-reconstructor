template <typename T> struct Tree;
struct Outer {
    struct Inner {};
    Tree<Inner>* tree;
};
template <> struct Tree<Outer::Inner> { int value; };
static_assert(sizeof(Tree<Outer::Inner>) == sizeof(int));
