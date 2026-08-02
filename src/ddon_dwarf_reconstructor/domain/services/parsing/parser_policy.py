"""Shared policies used by the class-parser discovery services."""

TYPE_BLACKLIST = {
    "pthread_mutex",
    "pthread_mutex_t",
    "pthread_cond",
    "pthread_cond_t",
    "pthread_rwlock",
    "pthread_rwlock_t",
    "pthread_attr_t",
    "FILE",
    "_IO_FILE",
    "__va_list_tag",
    "__builtin_va_list",
}

MAX_NON_IMPROVING_COMPLETE_CANDIDATES = 4
DWARF_ACCESS_NAMES = {1: "public", 2: "protected", 3: "private"}
