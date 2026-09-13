"""Application configuration management for the DWARF reconstructor."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _load_dotenv_if_present(env_path: Path | None) -> None:
    target = env_path or (Path.cwd() / ".env")
    if target.exists():
        try:
            from dotenv import load_dotenv

            load_dotenv(target)
        except ImportError:
            pass


def _env_path(primary: str, fallback: str | None = None) -> Path | None:
    raw = os.getenv(primary)
    if not raw and fallback:
        raw = os.getenv(fallback)
    return Path(raw) if raw else None


def _env_bool(name: str, default: bool = False) -> bool:
    val = os.getenv(name)
    if val is None:
        return default
    return val.lower() in ("true", "1", "yes")


@dataclass
class Config:
    """Application configuration."""

    elf_file_path: Path
    output_dir: Path
    verbose: bool = False
    log_dir: Path = Path("logs")
    dwarf_store_manifest: Path | None = None
    orbis_objdump: Path | None = None
    orbis_as: Path | None = None
    llvm_readobj: Path | None = None
    llvm_objdump: Path | None = None

    @classmethod
    def from_env(cls, env_path: Path | None = None) -> Config:
        """
        Load configuration from environment variables or .env file.

        Args:
            env_path: Optional path to .env file (defaults to .env in current directory)

        Returns:
            Config object
        """
        _load_dotenv_if_present(env_path)

        elf_file_path = _env_path("ELF_FILE_PATH") or Path("resources/DDOORBIS.elf")
        output_dir = _env_path("OUTPUT_DIR") or Path("output")
        verbose = _env_bool("VERBOSE", False)

        return cls(
            elf_file_path=elf_file_path,
            output_dir=output_dir,
            verbose=verbose,
            dwarf_store_manifest=_env_path("DWARF_STORE_MANIFEST", "DDON_DWARF_STORE"),
            orbis_objdump=_env_path("ORBIS_OBJDUMP_PATH", "DDON_ORBIS_OBJDUMP"),
            orbis_as=_env_path("ORBIS_AS_PATH", "DDON_ORBIS_AS"),
            llvm_readobj=_env_path("LLVM_READOBJ_PATH", "DDON_LLVM_READOBJ"),
            llvm_objdump=_env_path("LLVM_OBJDUMP_PATH", "DDON_LLVM_OBJDUMP"),
        )

    @classmethod
    def from_args(
        cls,
        elf_file_path: Path | None = None,
        output_dir: Path | None = None,
        verbose: bool | None = None,
        dwarf_store_manifest: Path | None = None,
        orbis_objdump: Path | None = None,
        orbis_as: Path | None = None,
        llvm_readobj: Path | None = None,
        llvm_objdump: Path | None = None,
    ) -> Config:
        """
        Create configuration from explicit arguments, falling back to environment.

        Args:
            elf_file_path: Path to ELF file (overrides env)
            output_dir: Output directory (overrides env)
            verbose: Enable verbose output (overrides env)
            dwarf_store_manifest: Path to DWARF store manifest (overrides env)
            orbis_objdump: Path to orbis-objdump (overrides env)
            orbis_as: Path to orbis-as (overrides env)
            llvm_readobj: Path to llvm-readobj (overrides env)
            llvm_objdump: Path to llvm-objdump (overrides env)

        Returns:
            Config object
        """
        # Start with env config
        config = cls.from_env()

        # Override with provided arguments
        if elf_file_path is not None:
            config.elf_file_path = elf_file_path
        if output_dir is not None:
            config.output_dir = output_dir
        if verbose is not None:
            config.verbose = verbose
        if dwarf_store_manifest is not None:
            config.dwarf_store_manifest = dwarf_store_manifest
        if orbis_objdump is not None:
            config.orbis_objdump = orbis_objdump
        if orbis_as is not None:
            config.orbis_as = orbis_as
        if llvm_readobj is not None:
            config.llvm_readobj = llvm_readobj
        if llvm_objdump is not None:
            config.llvm_objdump = llvm_objdump

        return config

    def validate(self) -> None:
        """
        Validate the configuration.

        Raises:
            ValueError: If configuration is invalid
        """
        if not self.elf_file_path.exists():
            raise ValueError(f"ELF file not found: {self.elf_file_path}")

        if not self.elf_file_path.is_file():
            raise ValueError(f"Not a file: {self.elf_file_path}")

    def ensure_output_dir(self) -> None:
        """Create the output directory if it doesn't exist."""
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def ensure_log_dir(self) -> None:
        """Create the log directory if it doesn't exist."""
        self.log_dir.mkdir(parents=True, exist_ok=True)
