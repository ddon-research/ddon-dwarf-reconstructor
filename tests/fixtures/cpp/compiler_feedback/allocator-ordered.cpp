#include "allocator-alloc.h"
#include "allocator-wrap.h"
static_assert(sizeof(Wrap<int>) >= sizeof(Alloc<int>));
