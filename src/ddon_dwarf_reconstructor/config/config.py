"""Configuration management for the DWARF reconstructor."""

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class Config:
    """Configuration for the DWARF reconstructor."""

    elf_file_path: Path
    output_dir: Path
    verbose: bool = False
    log_dir: Path = Path("logs")

    @classmethod
    def from_env(cls, env_path: Optional[Path] = None) -> "Config":
        """
        Load configuration from environment variables or .env file.

        Args:
            env_path: Optional path to .env file (defaults to .env in current directory)

        Returns:
            Config object
        """
        # Try to load from .env file if it exists
        if env_path is None:
            env_path = Path.cwd() / ".env"

        if env_path.exists():
            try:
                from dotenv import load_dotenv

                load_dotenv(env_path)
            except ImportError:
                # dotenv not available, will use environment variables only
                pass

        # Get configuration from environment variables
        elf_file_path_str = os.getenv("ELF_FILE_PATH", "resources/DDOORBIS.elf")
        output_dir_str = os.getenv("OUTPUT_DIR", "output")
        verbose_str = os.getenv("VERBOSE", "false").lower()

        elf_file_path = Path(elf_file_path_str)
        output_dir = Path(output_dir_str)
        verbose = verbose_str in ("true", "1", "yes")

        return cls(
            elf_file_path=elf_file_path, output_dir=output_dir, verbose=verbose
        )

    @classmethod
    def from_args(
        cls,
        elf_file_path: Optional[Path] = None,
        output_dir: Optional[Path] = None,
        verbose: Optional[bool] = None,
    ) -> "Config":
        """
        Create configuration from explicit arguments, falling back to environment.

        Args:
            elf_file_path: Path to ELF file (overrides env)
            output_dir: Output directory (overrides env)
            verbose: Enable verbose output (overrides env)

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
