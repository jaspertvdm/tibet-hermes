"""Tests for tibet-hermes installer module."""

import shutil
from pathlib import Path

import pytest

from tibet_hermes.installer import install_skill, install_mcp_config, install_memory_plugin


@pytest.fixture
def hermes_home(tmp_path):
    """Temporary ~/.hermes directory."""
    return tmp_path / ".hermes"


class TestInstallSkill:
    def test_creates_skill_directory(self, hermes_home):
        result = install_skill(hermes_home)
        assert result.exists()
        assert result == hermes_home / "skills" / "tibet-trust"

    def test_copies_skill_md(self, hermes_home):
        install_skill(hermes_home)
        skill_md = hermes_home / "skills" / "tibet-trust" / "SKILL.md"
        assert skill_md.exists()
        content = skill_md.read_text()
        assert "tibet" in content.lower()

    def test_idempotent(self, hermes_home):
        install_skill(hermes_home)
        install_skill(hermes_home)  # should not raise
        skill_md = hermes_home / "skills" / "tibet-trust" / "SKILL.md"
        assert skill_md.exists()


class TestInstallMcpConfig:
    def test_creates_new_config(self, hermes_home):
        result = install_mcp_config(hermes_home)
        assert result.exists()
        content = result.read_text()
        assert "tibet" in content.lower()
        assert "mcp:" in content
        assert "memory:" in content

    def test_custom_api_urls(self, hermes_home):
        install_mcp_config(
            hermes_home,
            tibet_api="http://custom:9000",
            ains_api="https://custom.aint",
        )
        content = (hermes_home / "config.yaml").read_text()
        assert "http://custom:9000" in content
        assert "https://custom.aint" in content

    def test_appends_to_existing(self, hermes_home):
        hermes_home.mkdir(parents=True, exist_ok=True)
        config = hermes_home / "config.yaml"
        config.write_text("existing: true\n")

        install_mcp_config(hermes_home)
        content = config.read_text()
        assert "existing: true" in content
        assert "tibet" in content.lower()

    def test_skips_if_tibet_present(self, hermes_home):
        hermes_home.mkdir(parents=True, exist_ok=True)
        config = hermes_home / "config.yaml"
        config.write_text("tibet: already_configured\n")

        install_mcp_config(hermes_home)
        content = config.read_text()
        # Should NOT have appended a duplicate
        assert content.count("mcp:") == 0


class TestInstallMemoryPlugin:
    def test_creates_plugin_dir(self, hermes_home):
        result = install_memory_plugin(hermes_home)
        assert result.exists()
        assert (result / "provider.py").exists()
        assert (result / "__init__.py").exists()

    def test_init_exports_provider(self, hermes_home):
        install_memory_plugin(hermes_home)
        init_content = (hermes_home / "plugins" / "memory" / "tibet" / "__init__.py").read_text()
        assert "TibetMemoryProvider" in init_content
        assert "Provider" in init_content
