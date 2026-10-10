#include "allocator-wrap.h"
#include "allocator-alloc.h"
static_assert(sizeof(Wrap<int>) >= sizeof(Alloc<int>));
