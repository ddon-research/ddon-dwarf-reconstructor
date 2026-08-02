"""Test the DWARF generator business logic with proper mocking."""

from pathlib import Path
from unittest.mock import Mock, mock_open

import pytest

from ddon_dwarf_reconstructor.application.generators import DwarfGenerator
from ddon_dwarf_reconstructor.infrastructure.elf_session import ElfDwarfSession


class TestDwarfGenerator:
    """Test suite for DwarfGenerator with proper mocking."""

    @pytest.mark.unit
    def test_resolve_dwarf_dump_path_prefers_explicit_argument(self, tmp_path: Path) -> None:
        """Explicit dwarf dump paths should win over environment or sibling discovery."""
        elf_path = tmp_path / "DDOORBIS.elf"
        elf_path.write_bytes(b"elf")
        explicit_dump = tmp_path / "explicit.zst"
        explicit_dump.write_bytes(b"dump")
        sibling_dump = tmp_path / "DDOORBIS.elf.llvmdwarfdump.zst"
        sibling_dump.write_bytes(b"sibling")

        generator = DwarfGenerator(
            elf_path,
            session_factory=ElfDwarfSession,
            exhaustive_search=False,
            dwarf_dump_path=explicit_dump,
            cache_file=tmp_path / "dwarf-cache.json",
        )

        assert generator._resolve_dwarf_dump_path() == explicit_dump

    @pytest.mark.unit
    def test_resolve_dwarf_dump_path_uses_environment_variable(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The DDON_DWARF_DUMP_PATH environment variable should be honored when present."""
        elf_path = tmp_path / "DDOORBIS.elf"
        elf_path.write_bytes(b"elf")
        env_dump = tmp_path / "env.zst"
        env_dump.write_bytes(b"dump")
        monkeypatch.setenv("DDON_DWARF_DUMP_PATH", str(env_dump))

        generator = DwarfGenerator(
            elf_path,
            session_factory=ElfDwarfSession,
            exhaustive_search=True,
            cache_file=tmp_path / "dwarf-cache.json",
        )

        assert generator._resolve_dwarf_dump_path() == env_dump

    @pytest.mark.unit
    def test_resolve_dwarf_dump_path_uses_sibling_dump(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The generator should auto-discover a sibling compressed dump for the same ELF."""
        elf_path = tmp_path / "DDOORBIS.elf"
        elf_path.write_bytes(b"elf")
        sibling_dump = tmp_path / "DDOORBIS.elf.llvmdwarfdump.zst"
        sibling_dump.write_bytes(b"dump")
        monkeypatch.delenv("DDON_DWARF_DUMP_PATH", raising=False)

        generator = DwarfGenerator(
            elf_path,
            session_factory=ElfDwarfSession,
            exhaustive_search=True,
            cache_file=tmp_path / "dwarf-cache.json",
        )

        assert generator._resolve_dwarf_dump_path() == sibling_dump

    @pytest.mark.unit
    def test_generator_initialization(self, mocker, tmp_path: Path):
        """Test DwarfGenerator initialization without file I/O."""
        mock_path = Path("test.elf")

        # Mock the file operations
        mocker.patch("pathlib.Path.exists", return_value=True)

        generator = DwarfGenerator(
            mock_path,
            session_factory=ElfDwarfSession,
            cache_file=tmp_path / "dwarf-cache.json",
        )

        assert generator.elf_path == mock_path
        assert generator.dwarf_info is None  # Not loaded yet

    @pytest.mark.unit
    def test_context_manager_behavior(self, mocker, mock_elf_file, tmp_path: Path):
        """Test context manager enters and exits properly with lazy loading."""
        mock_path = Path("test.elf")

        # Mock file operations and ELF parsing
        mocker.patch("pathlib.Path.exists", return_value=True)
        mocker.patch("pathlib.Path.mkdir", return_value=None)  # Mock cache directory creation
        mock_open_file = mocker.patch("builtins.open", mock_open())
        # Patch ELFFile where the infrastructure session constructs it.
        mocker.patch(
            "ddon_dwarf_reconstructor.infrastructure.elf_session.ELFFile",
            return_value=mock_elf_file,
        )

        with DwarfGenerator(
            mock_path,
            session_factory=ElfDwarfSession,
            cache_file=tmp_path / "dwarf-cache.json",
        ) as generator:
            assert generator.dwarf_info is not None
            # Verify new lazy loading components are initialized
            assert generator.type_resolver is not None
            assert generator.class_parser is not None
            assert generator.header_generator is not None
            assert generator.hierarchy_builder is not None
            assert generator.lazy_index is not None

        # Verify files were opened (ELF file + cache file)
        assert mock_open_file.call_count >= 1

    @pytest.mark.unit
    def test_find_class_success(
        self, mocker, mock_elf_file, mock_compilation_unit, mock_die, tmp_path: Path
    ):
        """Test finding a class by name successfully."""
        mock_path = Path("test.elf")

        # Setup mocks
        mocker.patch("pathlib.Path.exists", return_value=True)
        mocker.patch("builtins.open", mock_open())
        mocker.patch(
            "ddon_dwarf_reconstructor.infrastructure.elf_session.ELFFile",
            return_value=mock_elf_file,
        )

        mock_elf_file.get_dwarf_info.return_value.iter_CUs.return_value = [mock_compilation_unit]

        with DwarfGenerator(
            mock_path,
            session_factory=ElfDwarfSession,
            cache_file=tmp_path / "dwarf-cache.json",
        ) as generator:
            result = generator.find_class("MtObject")

        assert result == (mock_compilation_unit, mock_die)
        # Lazy loading may call iter_DIEs multiple times for different search strategies
        assert mock_compilation_unit.iter_DIEs.called

    @pytest.mark.unit
    def test_generate_header_structure(
        self, mocker, mock_elf_file, mock_compilation_unit, mock_die, tmp_path: Path
    ):
        """Test header generation returns proper C++ structure."""
        mock_path = Path("test.elf")

        # Setup mocks
        mocker.patch("pathlib.Path.exists", return_value=True)
        mocker.patch("builtins.open", mock_open())
        mocker.patch(
            "ddon_dwarf_reconstructor.infrastructure.elf_session.ELFFile",
            return_value=mock_elf_file,
        )

        mock_elf_file.get_dwarf_info.return_value.iter_CUs.return_value = [mock_compilation_unit]

        # Mock the get_parent method for all child DIEs to avoid complex parsing
        for child in mock_die.iter_children.return_value:
            if hasattr(child, "get_parent"):
                child.get_parent.return_value = mock_die
            else:
                child.get_parent = Mock(return_value=mock_die)

        with DwarfGenerator(
            mock_path,
            session_factory=ElfDwarfSession,
            cache_file=tmp_path / "dwarf-cache.json",
        ) as generator:
            header_content = generator.generate_header("MtObject")

        # Verify header contains expected C++ elements
        assert "#ifndef MTOBJECT_H" in header_content
        assert "class MtObject" in header_content
        assert "Generated from DWARF debug information" in header_content
        assert header_content.strip().endswith("#endif // MTOBJECT_H")

    @pytest.mark.unit
    def test_generate_header_builds_complete_standalone_closure(self, mocker):
        """Standalone generation must use the dependency-aware hierarchy builder."""
        generator = DwarfGenerator.__new__(DwarfGenerator)
        generator.class_parser = Mock()
        generator.type_resolver = Mock()
        generator.header_generator = Mock()
        generator.hierarchy_builder = Mock()
        generator.workflow = Mock()
        generator.workflow.generate_header.return_value = "header"

        header = DwarfGenerator.generate_header(generator, "Target", include_metadata=False)

        assert header == "header"
        generator.workflow.generate_header.assert_called_once_with("Target", False)

    @pytest.mark.unit
    def test_no_dwarf_info_error(self, mocker, tmp_path: Path):
        """Test proper error handling when ELF has no DWARF info."""
        mock_path = Path("test.elf")

        # Mock ELF file without DWARF
        mock_elf = Mock()
        mock_elf.has_dwarf_info.return_value = False

        mocker.patch("pathlib.Path.exists", return_value=True)
        mocker.patch("builtins.open", mock_open())
        mocker.patch(
            "ddon_dwarf_reconstructor.infrastructure.elf_session.ELFFile", return_value=mock_elf
        )

        with (
            pytest.raises(ValueError, match="No DWARF info found"),
            DwarfGenerator(
                mock_path,
                session_factory=ElfDwarfSession,
                cache_file=tmp_path / "dwarf-cache.json",
            ),
        ):
            # This should raise before we can do anything with the generator
            pass

    @pytest.mark.unit
    def test_file_not_found_error(self, mocker, tmp_path: Path):
        """Test proper error handling when ELF file doesn't exist."""
        mock_path = Path("nonexistent.elf")

        # Mock the open function to raise FileNotFoundError
        mocker.patch("builtins.open", side_effect=FileNotFoundError("File not found"))

        generator = DwarfGenerator(
            mock_path,
            session_factory=ElfDwarfSession,
            cache_file=tmp_path / "dwarf-cache.json",
        )

        # The error should occur when entering the context manager
        with pytest.raises(FileNotFoundError), generator:
            # Should not reach here due to file not found
            pass

    @pytest.mark.unit
    def test_failed_entry_closes_open_handle(self, mocker, tmp_path: Path) -> None:
        handle = Mock()
        mocker.patch("builtins.open", return_value=handle)
        mocker.patch(
            "ddon_dwarf_reconstructor.infrastructure.elf_session.ELFFile",
            side_effect=RuntimeError("invalid ELF"),
        )

        with (
            pytest.raises(RuntimeError, match="invalid ELF"),
            DwarfGenerator(
                Path("broken.elf"),
                session_factory=ElfDwarfSession,
                cache_file=tmp_path / "dwarf-cache.json",
            ),
        ):
            pass

        handle.close.assert_called_once_with()
