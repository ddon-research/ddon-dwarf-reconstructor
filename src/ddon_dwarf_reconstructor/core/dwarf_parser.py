"""DWARF Parser for extracting debug information from ELF files."""

import logging
import multiprocessing
import pickle
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import sys
import pickle
import logging
from hashlib import sha256
from pathlib import Path
from typing import Optional, Generator
from multiprocessing import Pool, cpu_count

from elftools.dwarf.die import DIE as ElfDIE
from elftools.elf.elffile import ELFFile

from ..utils.elf_patches import patch_pyelftools_for_ps4
from .models import CompilationUnit, DIE, DIEReference, DWARFAttribute

# Apply PS4 ELF patches on module load
patch_pyelftools_for_ps4()

logger = logging.getLogger(__name__)


def _parse_cu_worker(args: tuple) -> Optional[CompilationUnit]:
    """Worker function for parallel CU parsing.

    Args:
        args: Tuple of (elf_path, cu_offset, cache_dir, use_cache)

    Returns:
        Parsed CompilationUnit or None on failure
    """
    elf_path, cu_offset, cache_dir, use_cache = args

    try:
        # Each worker opens its own ELF file
        parser = DWARFParser(elf_path, verbose=False, cache_dir=cache_dir)
        parser.open()
        parser.load_dwarf_info()

        # Find the CU with the matching offset
        for cu in parser.dwarf_info.iter_CUs():
            if cu.cu_offset == cu_offset:
                comp_unit = parser.parse_compilation_unit(cu, use_cache=use_cache)
                parser.close()
                return comp_unit

        parser.close()
        return None

    except Exception as e:
        logger.warning(f"Worker failed to parse CU at offset 0x{cu_offset:08x}: {e}")
        return None


class DWARFParser:
    """Parser for extracting DWARF debug information from ELF files."""

    def __init__(self, elf_path: Path, verbose: bool = False, cache_dir: Optional[Path] = None) -> None:
        """
        Initialize the DWARF parser.

        Args:
            elf_path: Path to the ELF file
            verbose: Enable verbose output
            cache_dir: Directory for CU cache files (default: .dwarf_cache)
        """
        self.elf_path = elf_path
        self.verbose = verbose
        self.elf_file: Optional[ELFFile] = None
        self.dwarf_info: Optional[any] = None
        self.cache_dir = cache_dir or Path(".dwarf_cache")
        self._elf_cache_key: Optional[str] = None

    def open(self) -> None:
        """Open and validate the ELF file."""
        if not self.elf_path.exists():
            raise FileNotFoundError(f"ELF file not found: {self.elf_path}")

        if not self.elf_path.is_file():
            raise ValueError(f"Not a file: {self.elf_path}")

        try:
            # Open file handle (keep it open for the lifetime of the parser)
            self.file_handle = open(self.elf_path, "rb")
            self.elf_file = ELFFile(self.file_handle, stream_loader=None)

            if self.verbose:
                print(f"Opened ELF file: {self.elf_path}")
                print(f"Architecture: {self.elf_file.get_machine_arch()}")

        except Exception as e:
            if hasattr(self, "file_handle"):
                self.file_handle.close()
            raise RuntimeError(f"Failed to open ELF file: {e}") from e

    def load_dwarf_info(self) -> None:
        """Load DWARF debug information from the ELF file."""
        if not self.elf_file:
            raise RuntimeError("ELF file not opened. Call open() first.")

        try:
            # PS4 ELF files may have non-standard sections that cause issues
            # Try to get DWARF info directly without checking has_dwarf_info()
            try:
                self.dwarf_info = self.elf_file.get_dwarf_info()
            except Exception as dwarf_err:
                # If direct access fails, try to check if DWARF sections exist
                if self.verbose:
                    print(f"Direct DWARF access failed: {dwarf_err}")
                    print("Attempting alternative DWARF section detection...")

                # Try to find debug sections manually
                has_debug_section = False
                try:
                    for section in self.elf_file.iter_sections():
                        if section.name.startswith('.debug_'):
                            has_debug_section = True
                            break
                except Exception:
                    pass

                if not has_debug_section:
                    raise ValueError(
                        f"No DWARF debug information found in {self.elf_path}. "
                        "This PS4 ELF file may not contain debug symbols."
                    )

                # If we found debug sections but can't load them, re-raise
                raise ValueError(
                    f"DWARF sections found but cannot be loaded due to PS4-specific "
                    f"ELF format issues: {dwarf_err}"
                ) from dwarf_err

            if not self.dwarf_info:
                raise ValueError(
                    f"No DWARF debug information found in {self.elf_path}"
                )

            if self.verbose:
                print("DWARF information loaded successfully")
                print(
                    f"DWARF version: "
                    f"{self.dwarf_info.config.default_address_size * 8}-bit"
                )

        except Exception as e:
            raise RuntimeError(f"Failed to load DWARF info: {e}") from e

    def parse_die(self, elf_die: ElfDIE, level: int = 0) -> DIE:
        """
        Parse an ELF DIE into our DIE model.

        Args:
            elf_die: The pyelftools DIE object
            level: The nesting level of this DIE

        Returns:
            Parsed DIE object
        """
        # Create the DIE
        die = DIE(
            level=level,
            offset=elf_die.offset,
            global_offset=elf_die.cu.cu_offset + elf_die.offset,
            tag=elf_die.tag,
        )

        # Parse attributes
        for attr_name, attr in elf_die.attributes.items():
            # Handle different attribute types
            value: any = None
            raw_value = str(attr.value)

            if attr.form == "DW_FORM_ref4" or attr.form.startswith("DW_FORM_ref"):
                # This is a reference to another DIE
                ref_offset = attr.value
                # Calculate the global offset (CU offset + reference offset)
                global_offset = elf_die.cu.cu_offset + ref_offset
                value = DIEReference(offset=ref_offset, global_offset=global_offset)
            elif attr.form == "DW_FORM_strp" or attr.form == "DW_FORM_string":
                # String value
                value = attr.value.decode("utf-8") if isinstance(
                    attr.value, bytes
                ) else str(attr.value)
            elif attr.form in ["DW_FORM_data1", "DW_FORM_data2", "DW_FORM_data4",
                              "DW_FORM_data8", "DW_FORM_udata", "DW_FORM_sdata"]:
                # Numeric value
                value = int(attr.value)
            elif attr.form == "DW_FORM_flag" or attr.form == "DW_FORM_flag_present":
                # Boolean value
                value = bool(attr.value)
            elif attr.form == "DW_FORM_addr":
                # Address value
                value = int(attr.value)
            elif attr.form in ["DW_FORM_block", "DW_FORM_block1", "DW_FORM_block2",
                              "DW_FORM_block4", "DW_FORM_exprloc"]:
                # Block of data (used for location expressions, etc.)
                value = bytes(attr.value) if isinstance(attr.value, list) else attr.value
            else:
                # Default: keep as-is
                value = attr.value

            die.attributes[attr_name] = DWARFAttribute(
                name=attr_name, value=value, raw_value=raw_value
            )

        return die

    def _get_elf_cache_key(self) -> str:
        """Generate cache key for the ELF file."""
        if self._elf_cache_key is None:
            file_data = self.elf_path.read_bytes()[:4096]
            file_hash = sha256(file_data).hexdigest()[:16]
            mtime = int(self.elf_path.stat().st_mtime)
            self._elf_cache_key = f"{self.elf_path.stem}_{file_hash}_{mtime}"
        return self._elf_cache_key

    def _get_cu_cache_path(self, cu_offset: int) -> Path:
        """Get cache file path for a specific CU."""
        cache_key = self._get_elf_cache_key()
        return self.cache_dir / f"{cache_key}_cu_{cu_offset:08x}.pkl"

    def _load_cu_from_cache(self, cu_offset: int) -> Optional[CompilationUnit]:
        """Load a cached compilation unit."""
        cache_path = self._get_cu_cache_path(cu_offset)
        if not cache_path.exists():
            return None

        try:
            with cache_path.open("rb") as f:
                cu = pickle.load(f)
            return cu
        except Exception as e:
            logger.warning(f"Failed to load CU cache from {cache_path}: {e}")
            cache_path.unlink(missing_ok=True)
            return None

    def _save_cu_to_cache(self, cu: CompilationUnit) -> None:
        """Save a compilation unit to cache."""
        cache_path = self._get_cu_cache_path(cu.offset)

        try:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            with cache_path.open("wb") as f:
                pickle.dump(cu, f, protocol=pickle.HIGHEST_PROTOCOL)
        except Exception as e:
            logger.warning(f"Failed to save CU cache to {cache_path}: {e}")

    def parse_compilation_unit(self, cu: any, use_cache: bool = True) -> CompilationUnit:
        """
        Parse a compilation unit and all its DIEs with optional caching.

        Args:
            cu: The pyelftools compilation unit
            use_cache: Whether to use CU-level caching (default: True)

        Returns:
            Parsed CompilationUnit object
        """
        import time

        # Try to load from cache
        if use_cache:
            cached_cu = self._load_cu_from_cache(cu.cu_offset)
            if cached_cu is not None:
                return cached_cu

        # Parse from scratch
        parse_start = time.time()

        comp_unit = CompilationUnit(
            offset=cu.cu_offset,
            size=cu.size,
            version=cu.header.version,
            address_size=cu.header.address_size,
        )

        # Parse all DIEs in this CU
        def parse_die_recursive(elf_die: ElfDIE, level: int, parent: Optional[DIE]) -> DIE:
            die = self.parse_die(elf_die, level)
            die.parent = parent
            comp_unit.dies.append(die)

            # Parse children
            for child in elf_die.iter_children():
                child_die = parse_die_recursive(child, level + 1, die)
                die.children.append(child_die)

            return die

        # Start parsing from the top-level DIE of the CU
        top_die = cu.get_top_DIE()
        parse_die_recursive(top_die, 0, None)

        parse_time = time.time() - parse_start

        # Save to cache
        if use_cache:
            self._save_cu_to_cache(comp_unit)

        return comp_unit

    def parse_all_compilation_units(
        self, max_cus: Optional[int] = None, parallel: bool = False, workers: Optional[int] = None
    ) -> list[CompilationUnit]:
        """
        Parse all compilation units in the DWARF info.

        Args:
            max_cus: Optional maximum number of CUs to parse (for memory management)
            parallel: Use parallel processing (default: False)
            workers: Number of worker processes (default: cpu_count())

        Returns:
            List of parsed CompilationUnit objects
        """
        import logging
        import time

        logger = logging.getLogger(__name__)

        if not self.dwarf_info:
            raise RuntimeError("DWARF info not loaded. Call load_dwarf_info() first.")

        # If parallel processing requested, use worker pool
        if parallel:
            return self._parse_all_parallel(max_cus, workers)

        start_time = time.time()
        compilation_units: list[CompilationUnit] = []

        limit_msg = f" (limit: {max_cus})" if max_cus else " (no limit)"
        logger.info(f"Starting to parse compilation units{limit_msg}...")

        cu_count = 0
        total_dies = 0
        cu_times = []
        cache_hits = 0
        cache_misses = 0

        for cu in self.dwarf_info.iter_CUs():
            if max_cus and cu_count >= max_cus:
                logger.info(f"Reached CU limit of {max_cus}, stopping")
                break

            try:
                cu_start = time.time()

                # Check if CU exists in cache before parsing
                cached_cu = self._load_cu_from_cache(cu.cu_offset)
                if cached_cu:
                    comp_unit = cached_cu
                    cache_hits += 1
                    cu_elapsed = time.time() - cu_start
                else:
                    comp_unit = self.parse_compilation_unit(cu, use_cache=True)
                    cache_misses += 1
                    cu_elapsed = time.time() - cu_start

                compilation_units.append(comp_unit)
                cu_count += 1
                total_dies += len(comp_unit.dies)
                cu_times.append(cu_elapsed)

                # Log every 10 CUs to avoid spam
                if cu_count % 10 == 0 or self.verbose:
                    status = "cached" if cached_cu else "parsed"
                    logger.info(
                        f"  CU {cu_count}/{max_cus or '?'} "
                        f"(offset: 0x{comp_unit.offset:08x}, "
                        f"{len(comp_unit.dies)} DIEs, "
                        f"{status}, {cu_elapsed:.3f}s)"
                    )
            except Exception as e:
                logger.warning(
                    f"Failed to parse CU at offset 0x{cu.cu_offset:08x}: {e}"
                )
                cache_misses += 1

        total_time = time.time() - start_time
        avg_cu_time = sum(cu_times) / len(cu_times) if cu_times else 0
        cache_hit_rate = (cache_hits / cu_count * 100) if cu_count > 0 else 0

        logger.info(
            f"✓ Parsed {len(compilation_units)} CUs with {total_dies:,} total DIEs "
            f"in {total_time:.2f}s (avg: {avg_cu_time:.3f}s/CU)\n"
            f"  Cache: {cache_hits} hits, {cache_misses} misses ({cache_hit_rate:.1f}% hit rate)"
        )

        return compilation_units

    def parse_cus_until_target_found(
        self, 
        target_symbol: str, 
        max_cus: Optional[int] = None
    ) -> tuple[list[CompilationUnit], bool]:
        """Parse CUs sequentially until target symbol is found or limit reached.
        
        Args:
            target_symbol: Symbol name to search for in each CU
            max_cus: Maximum CUs to parse before giving up
            
        Returns:
            Tuple of (parsed_compilation_units, found_target)
        """
        logger = logging.getLogger(__name__)
        
        if not self.dwarf_info:
            raise RuntimeError("DWARF info not loaded. Call load_dwarf_info() first.")
            
        start_time = time.time()
        compilation_units: list[CompilationUnit] = []
        
        limit_msg = f" (searching max {max_cus} CUs)" if max_cus else " (no limit)"
        logger.info(f"Starting CU parsing with early stop for '{target_symbol}'{limit_msg}...")
        
        cu_count = 0
        total_dies = 0
        cu_times = []
        cache_hits = 0
        cache_misses = 0
        found_target = False
        
        for cu in self.dwarf_info.iter_CUs():
            if max_cus and cu_count >= max_cus:
                logger.info(f"Reached CU limit of {max_cus}, stopping search")
                break
                
            try:
                cu_start = time.time()
                
                # Check if CU exists in cache before parsing
                cached_cu = self._load_cu_from_cache(cu.cu_offset)
                if cached_cu:
                    comp_unit = cached_cu
                    cache_hits += 1
                    cu_elapsed = time.time() - cu_start
                else:
                    comp_unit = self.parse_compilation_unit(cu, use_cache=True)
                    cache_misses += 1
                    cu_elapsed = time.time() - cu_start
                    
                compilation_units.append(comp_unit)
                cu_count += 1
                total_dies += len(comp_unit.dies)
                cu_times.append(cu_elapsed)
                
                # Check if target symbol is in this CU
                target_found_in_cu = self._check_cu_contains_class(comp_unit, target_symbol)
                
                status = "cached" if cached_cu else "parsed"
                target_status = f", FOUND '{target_symbol}'!" if target_found_in_cu else ""
                
                logger.info(
                    f"  CU {cu_count} "
                    f"(offset: 0x{comp_unit.offset:08x}, "
                    f"{len(comp_unit.dies)} DIEs, "
                    f"{status}, {cu_elapsed:.3f}s){target_status}"
                )
                
                if target_found_in_cu:
                    found_target = True
                    logger.info(f"✓ Early stop: Found '{target_symbol}' in CU {cu_count}")
                    break
                    
            except Exception as e:
                logger.warning(
                    f"Failed to parse CU at offset 0x{cu.cu_offset:08x}: {e}"
                )
                cache_misses += 1
                
        total_time = time.time() - start_time
        avg_cu_time = sum(cu_times) / len(cu_times) if cu_times else 0
        cache_hit_rate = (cache_hits / cu_count * 100) if cu_count > 0 else 0
        
        result_msg = "FOUND" if found_target else "NOT FOUND"
        logger.info(
            f"✓ Parsed {len(compilation_units)} CUs with {total_dies:,} total DIEs "
            f"in {total_time:.2f}s (avg: {avg_cu_time:.3f}s/CU) - Target: {result_msg}\n"
            f"  Cache: {cache_hits} hits, {cache_misses} misses ({cache_hit_rate:.1f}% hit rate)"
        )
        
        return compilation_units, found_target
        
    def _check_cu_contains_class(self, cu: CompilationUnit, target_symbol: str) -> bool:
        """Fast check if CU contains a class with the given name.
        
        Args:
            cu: Compilation unit to search
            target_symbol: Class name to look for
            
        Returns:
            True if class found, False otherwise
        """
        class_tags = {'DW_TAG_class_type', 'DW_TAG_structure_type', 'DW_TAG_union_type'}
        
        for die in cu.dies:
            if die.tag in class_tags:
                name = die.get_name()
                if name == target_symbol:
                    return True
        return False

    def _parse_all_parallel(
        self, max_cus: Optional[int] = None, workers: Optional[int] = None
    ) -> list[CompilationUnit]:
        """Parse CUs in parallel using multiprocessing.

        Args:
            max_cus: Maximum number of CUs to parse
            workers: Number of worker processes (default: cpu_count())

        Returns:
            List of parsed CompilationUnit objects
        """
        import time

        start_time = time.time()

        # Collect CU offsets first
        cu_offsets = []
        for cu in self.dwarf_info.iter_CUs():
            cu_offsets.append(cu.cu_offset)
            if max_cus and len(cu_offsets) >= max_cus:
                break

        if not cu_offsets:
            return []

        # Determine worker count
        num_workers = workers or cpu_count()
        num_workers = min(num_workers, len(cu_offsets))  # Don't create more workers than CUs

        logger.info(
            f"Parsing {len(cu_offsets)} CUs in parallel using {num_workers} workers..."
        )

        # Prepare arguments for workers
        worker_args = [
            (self.elf_path, offset, self.cache_dir, True) for offset in cu_offsets
        ]

        # Parse in parallel
        with Pool(num_workers) as pool:
            compilation_units = pool.map(_parse_cu_worker, worker_args)

        # Filter out None results (failed parses)
        compilation_units = [cu for cu in compilation_units if cu is not None]

        total_time = time.time() - start_time
        total_dies = sum(len(cu.dies) for cu in compilation_units)

        logger.info(
            f"✓ Parsed {len(compilation_units)} CUs with {total_dies:,} total DIEs "
            f"in {total_time:.2f}s using {num_workers} workers "
            f"(avg: {total_time/len(compilation_units):.3f}s/CU)"
        )

        return compilation_units

    def iter_compilation_units(self) -> "Generator[CompilationUnit, None, None]":
        """
        Iterator that yields compilation units one by one for efficient scanning.

        This allows processing CUs incrementally without loading all into memory,
        which is crucial for performance when searching for specific symbols.

        Yields:
            CompilationUnit objects one at a time
        """
        if not self.dwarf_info:
            raise RuntimeError("DWARF info not loaded. Call load_dwarf_info() first.")

        for cu in self.dwarf_info.iter_CUs():
            try:
                comp_unit = self.parse_compilation_unit(cu)
                yield comp_unit
            except Exception as e:
                if self.verbose:
                    print(
                        f"  Warning: Failed to parse CU at offset "
                        f"0x{cu.cu_offset:08x}: {e}",
                        file=sys.stderr,
                    )
                continue

    def find_symbol_cu(self, symbol_name: str, max_cus: Optional[int] = None) -> Optional[CompilationUnit]:
        """
        Find the compilation unit containing a specific symbol.

        This is a memory-efficient way to locate a symbol without parsing all CUs.
        Only parses CUs until the symbol is found.

        Args:
            symbol_name: Symbol name to search for
            max_cus: Maximum CUs to scan before giving up (None = unlimited)

        Returns:
            CompilationUnit containing the symbol, or None if not found
        """
        if not self.dwarf_info:
            raise RuntimeError("DWARF info not loaded. Call load_dwarf_info() first.")

        cu_count = 0
        for cu in self.dwarf_info.iter_CUs():
            if max_cus and cu_count >= max_cus:
                if self.verbose:
                    print(f"  Symbol '{symbol_name}' not found in first {max_cus} CUs")
                return None

            try:
                comp_unit = self.parse_compilation_unit(cu)
                cu_count += 1

                # Quick check for symbol in this CU
                for die in comp_unit.dies:
                    if die.get_name() == symbol_name:
                        if self.verbose:
                            print(
                                f"  Found '{symbol_name}' in CU {cu_count} "
                                f"at offset 0x{comp_unit.offset:08x}"
                            )
                        return comp_unit

            except Exception as e:
                if self.verbose:
                    print(
                        f"  Warning: Failed to parse CU at offset "
                        f"0x{cu.cu_offset:08x}: {e}",
                        file=sys.stderr,
                    )
                continue

        if self.verbose:
            print(f"  Symbol '{symbol_name}' not found in {cu_count} CUs")
        return None

    def close(self) -> None:
        """Close the ELF file."""
        if hasattr(self, "file_handle"):
            self.file_handle.close()

    def __enter__(self) -> "DWARFParser":
        """Context manager entry."""
        self.open()
        self.load_dwarf_info()
        return self

    def __exit__(self, exc_type: any, exc_val: any, exc_tb: any) -> None:
        """Context manager exit."""
        self.close()
