#pragma once
template <typename T> class Alloc;
template <typename T> class Wrap;
template <> class Alloc<int> { Wrap<int>* next; };
