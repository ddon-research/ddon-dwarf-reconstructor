# DWARF Search Indexing Strategy

Implementation date: 2025-10-06
Based on: Ghidra DWARF parser insights (`dwarf/ghidra-dwarf-parsing.md`)

## Overview

The DIEExtractor now implements lazy-loaded indexes for fast symbol lookup, avoiding the need to scan all compilation units for every search.

## Performance Results

**Test Configuration**: 10 compilation units, 476,101 DIEs

| Operation | First Call (Build Index) | Subsequent Calls (Cached) | Speedup |
|-----------|-------------------------|---------------------------|---------|
| Name search | 167.89ms | 0.00ms | ~60,000x |
| Tag search | 84.65ms | 0.48ms | ~176x |
| Offset lookup | 99.92ms | N/A | N/A |

## Implementation Details

### Three Lazy-Loaded Indexes

#### 1. Name Index
```python
_name_index: dict[str, list[tuple[int, DIE]]]
```
- Maps symbol name → list of (CU index, DIE) tuples
- Built on first `find_dies_by_name()` call
- Enables O(1) name lookups instead of O(n) scans
- 41,671 entries for 10 CUs

#### 2. Tag Index
```python
_tag_index: dict[str, list[tuple[int, DIE]]]
```
- Maps DWARF tag → list of (CU index, DIE) tuples
- Built on first `find_dies_by_tag()` call
- Fast retrieval of all classes, structs, functions, etc.
- 32 entries (one per unique DWARF tag)

#### 3. Offset Index
```python
_offset_index: dict[int, tuple[int, DIE]]
```
- Maps DIE offset → (CU index, DIE) tuple
- Built on first `get_die_by_offset()` call
- Enables O(1) DIE reference resolution
- 476,101 entries for 10 CUs (one per DIE)

### Lazy Loading Pattern

Indexes are **not** built at initialization. Instead:
1. First search builds the index (one-time cost)
2. Subsequent searches use cached index (near-instant)
3. Memory only consumed when needed

```python
def find_dies_by_name(self, name: str) -> list[tuple[CompilationUnit, DIE]]:
    self._build_name_index()  # Builds only once, no-op thereafter
    indexed_results = self._name_index.get(name, [])
    return [(self.compilation_units[cu_idx], die) for cu_idx, die in indexed_results]
```

## Design Rationale

### Why Lazy Instead of Eager?

**Eager (build all indexes at init)**:
- ❌ High upfront cost even if indexes never used
- ❌ All three indexes consume memory simultaneously
- ❌ Slows down initialization

**Lazy (build on first use)**:
- ✅ Zero cost if index never needed
- ✅ Only pay for what you use
- ✅ Fast initialization
- ✅ Memory allocated incrementally

### Why Index-Based References?

Following Ghidra's approach, we store:
- CU index (int) instead of CU reference
- Avoids circular references
- Lighter memory footprint
- Easy to serialize/cache to disk (future enhancement)

## Memory Usage

For 10 CUs with 476,101 DIEs:
- **Name index**: ~41,671 entries × ~40 bytes ≈ 1.6 MB
- **Tag index**: ~32 entries × ~1,000 bytes ≈ 32 KB
- **Offset index**: ~476,101 entries × ~24 bytes ≈ 11 MB

**Total**: ~13 MB for fast lookups across 10 CUs

For full 2,305 CUs:
- Estimated ~3 GB for complete indexing
- But only allocated if indexes actually used

## Trade-offs

### Advantages
1. **Massive speedup** for repeated searches (~60,000x)
2. **No upfront cost** if indexes not needed
3. **Memory-efficient** for single searches (no index built)
4. **Scalable** to large DWARF files

### Limitations
1. **Memory cost** when index built (~13 MB per 10 CUs)
2. **First search slower** (builds index)
3. **Stale indexes** if CUs modified (not an issue for read-only parsing)

## Comparison with Other Approaches

### pyelftools (Original)
- **Strategy**: Linear scan every search
- **Speed**: Slow for repeated searches
- **Memory**: Low (no indexes)
- **Best for**: Single searches, small files

### Ghidra
- **Strategy**: Lazy loading + index-based trees
- **Speed**: Fast (optimized for production)
- **Memory**: Very low (index-based relationships)
- **Best for**: Large files, production use

### Our Implementation (Hybrid)
- **Strategy**: Lazy indexes + full DIE objects
- **Speed**: Fast for repeated searches
- **Memory**: Moderate (indexes cached, DIEs in memory)
- **Best for**: Medium files, multiple searches

## Future Enhancements

### 1. Persistent Index Cache
Save built indexes to disk:
```python
# .dwarf_cache/DDOORBIS.elf.name_index.pkl
# Reuse across runs without rebuilding
```

### 2. Partial Indexing
Index only specific CUs:
```python
extractor.build_index_for_cu_range(0, 100)
```

### 3. Memory-Mapped Indexes
Use mmap for very large indexes:
```python
# Load index from disk without full memory load
```

### 4. Index-Based DIE Relationships
Following Ghidra, replace parent/child references with indices:
```python
class DIE:
    parent_index: Optional[int]  # Instead of parent: Optional[DIE]
    child_indices: list[int]      # Instead of children: list[DIE]
```

## Recommendations

### When to Use Indexing

**Use indexed search** (`DIEExtractor`) when:
- Multiple searches needed
- Searching for various symbols
- Memory available (~3 GB for full index)

**Use direct iteration** (`quick_search.py`) when:
- Single search only
- Very large file with limited memory
- Only need first match (early-exit)

### Memory Considerations

Monitor memory usage with:
```python
import sys
size = sys.getsizeof(extractor._name_index)
print(f"Name index: {size / 1024 / 1024:.1f} MB")
```

### Performance Tuning

For best performance:
1. Parse only needed CUs (not all 2,305)
2. Build specific indexes as needed
3. Reuse DIEExtractor instance across searches
4. Consider persistent cache for repeated runs

## References

- `docs/knowledge-base/dwarf/ghidra-dwarf-parsing.md` - Ghidra's lazy loading approach
- `docs/knowledge-base/pyelftools/pyelftools-approach.md` - pyelftools eager loading
- `tests/test_performance.py` - Performance benchmarks
