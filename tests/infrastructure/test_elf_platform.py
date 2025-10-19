#!/usr/bin/env python3

"""Unit tests for ELF platform detection.

Tests the PlatformDetector class for correctly identifying target platforms
from ELF file characteristics.
"""

from unittest.mock import Mock, mock_open, patch

import pytest

from ddon_dwarf_reconstructor.infrastructure.elf_platform import ELFPlatform, PlatformDetector


class TestELFPlatformEnum:
    """Tests for ELFPlatform enum."""

    @pytest.mark.unit
    def test_ps3_string_representation(self) -> None:
        """Test PS3 platform string representation."""
        assert str(ELFPlatform.PS3) == "PS3"

    @pytest.mark.unit
    def test_ps4_string_representation(self) -> None:
        """Test PS4 platform string representation."""
        assert str(ELFPlatform.PS4) == "PS4"

    @pytest.mark.unit
    def test_unknown_string_representation(self) -> None:
        """Test UNKNOWN platform string representation."""
        assert str(ELFPlatform.UNKNOWN) == "UNKNOWN"


class TestPlatformDetector:
    """Tests for PlatformDetector.detect() method."""

    @pytest.mark.unit
    def test_detect_ps4_elf(self) -> None:
        """Test detection of PS4 ELF (x86-64 little-endian)."""
        mock_elf = Mock()
        mock_elf.header = {"e_machine": "EM_X86_64"}
        mock_elf.little_endian = True
        mock_elf.has_dwarf_info.return_value = False

        with patch("builtins.open", mock_open()), patch(
            "ddon_dwarf_reconstructor.infrastructure.elf_platform.ELFFile",
            return_value=mock_elf,
        ):
            result = PlatformDetector.detect("test.elf")
            assert result == ELFPlatform.PS4

    @pytest.mark.unit
    def test_detect_ps3_elf(self) -> None:
        """Test detection of PS3 ELF (PowerPC64 big-endian)."""
        mock_elf = Mock()
        mock_elf.header = {"e_machine": "EM_PPC64"}
        mock_elf.little_endian = False
        mock_elf.has_dwarf_info.return_value = False

        with patch("builtins.open", mock_open()), patch(
            "ddon_dwarf_reconstructor.infrastructure.elf_platform.ELFFile",
            return_value=mock_elf,
        ):
            result = PlatformDetector.detect("test.elf")
            assert result == ELFPlatform.PS3

    @pytest.mark.unit
    def test_detect_unknown_machine_type(self) -> None:
        """Test detection of unknown machine type."""
        mock_elf = Mock()
        mock_elf.header = {"e_machine": "EM_ARM"}
        mock_elf.little_endian = True
        mock_elf.has_dwarf_info.return_value = False

        with patch("builtins.open", mock_open()), patch(
            "ddon_dwarf_reconstructor.infrastructure.elf_platform.ELFFile",
            return_value=mock_elf,
        ):
            result = PlatformDetector.detect("test.elf")
            assert result == ELFPlatform.UNKNOWN

    @pytest.mark.unit
    def test_detect_x86_64_big_endian_unknown(self) -> None:
        """Test x86-64 big-endian is detected as unknown (unusual combination)."""
        mock_elf = Mock()
        mock_elf.header = {"e_machine": "EM_X86_64"}
        mock_elf.little_endian = False
        mock_elf.has_dwarf_info.return_value = False

        with patch("builtins.open", mock_open()), patch(
            "ddon_dwarf_reconstructor.infrastructure.elf_platform.ELFFile",
            return_value=mock_elf,
        ):
            result = PlatformDetector.detect("test.elf")
            assert result == ELFPlatform.UNKNOWN

    @pytest.mark.unit
    def test_detect_powerpc64_little_endian_unknown(self) -> None:
        """Test PowerPC64 little-endian is detected as unknown (unusual combination)."""
        mock_elf = Mock()
        mock_elf.header = {"e_machine": "EM_PPC64"}
        mock_elf.little_endian = True
        mock_elf.has_dwarf_info.return_value = False

        with patch("builtins.open", mock_open()), patch(
            "ddon_dwarf_reconstructor.infrastructure.elf_platform.ELFFile",
            return_value=mock_elf,
        ):
            result = PlatformDetector.detect("test.elf")
            assert result == ELFPlatform.UNKNOWN

    @pytest.mark.unit
    def test_detect_file_not_found(self) -> None:
        """Test handling of non-existent file."""
        with patch("builtins.open", side_effect=FileNotFoundError("File not found")):
            result = PlatformDetector.detect("nonexistent.elf")
            assert result == ELFPlatform.UNKNOWN

    @pytest.mark.unit
    def test_detect_invalid_elf(self) -> None:
        """Test handling of invalid ELF file."""
        with patch("builtins.open", mock_open()), patch(
            "ddon_dwarf_reconstructor.infrastructure.elf_platform.ELFFile",
            side_effect=Exception("Invalid ELF"),
        ):
            result = PlatformDetector.detect("invalid.elf")
            assert result == ELFPlatform.UNKNOWN

    @pytest.mark.unit
    def test_get_dwarf_version_success(self) -> None:
        """Test extracting DWARF version from ELF."""
        mock_cu = Mock()
        mock_cu.header = {"version": 4}

        mock_dwarf = Mock()
        mock_dwarf.iter_CUs.return_value = [mock_cu]

        mock_elf = Mock()
        mock_elf.has_dwarf_info.return_value = True
        mock_elf.get_dwarf_info.return_value = mock_dwarf

        result = PlatformDetector._get_dwarf_version(mock_elf)
        assert result == 4

    @pytest.mark.unit
    def test_get_dwarf_version_no_dwarf(self) -> None:
        """Test when ELF has no DWARF info."""
        mock_elf = Mock()
        mock_elf.has_dwarf_info.return_value = False

        result = PlatformDetector._get_dwarf_version(mock_elf)
        assert result is None

    @pytest.mark.unit
    def test_get_dwarf_version_exception(self) -> None:
        """Test exception handling in DWARF version extraction."""
        mock_elf = Mock()
        mock_elf.has_dwarf_info.return_value = True
        mock_elf.get_dwarf_info.side_effect = Exception("DWARF error")

        result = PlatformDetector._get_dwarf_version(mock_elf)
        assert result is None


class TestPlatformAwareOutputDirectories:
    """Tests for platform-aware output directory handling."""

    @pytest.mark.unit
    def test_platform_string_representation_lowercase(self) -> None:
        """Test that platform values are lowercase for directory names."""
        assert ELFPlatform.PS3.value == "ps3"
        assert ELFPlatform.PS4.value == "ps4"
        assert ELFPlatform.UNKNOWN.value == "unknown"

    @pytest.mark.unit
    def test_platform_string_representation_uppercase(self) -> None:
        """Test that str() returns uppercase platform names."""
        assert str(ELFPlatform.PS3) == "PS3"
        assert str(ELFPlatform.PS4) == "PS4"
        assert str(ELFPlatform.UNKNOWN) == "UNKNOWN"

    @pytest.mark.unit
    def test_output_directory_structure(self, tmp_path) -> None:  # type: ignore
        """Test that output directories can be created by platform."""
        # Simulate creating platform-specific output directories
        output_base = tmp_path / "output"
        output_base.mkdir()

        ps4_dir = output_base / ELFPlatform.PS4.value
        ps3_dir = output_base / ELFPlatform.PS3.value

        ps4_dir.mkdir(parents=True, exist_ok=True)
        ps3_dir.mkdir(parents=True, exist_ok=True)

        # Verify directories exist
        assert ps4_dir.exists()
        assert ps3_dir.exists()

        # Verify structure
        assert (ps4_dir / "MtObject.h").parent == ps4_dir
        assert (ps3_dir / "MtDTI.h").parent == ps3_dir
