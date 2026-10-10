struct Node {};
struct Owner {
    template <typename T> class Helper;
    void use(Helper<Node>&);
};
