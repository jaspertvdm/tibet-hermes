"""tibet-hermes installer — drops skill + config into ~/.hermes/

Usage:
  tibet-hermes-install              # CLI entry point
  python -m tibet_hermes.installer  # direct

Or programmatic:
  from tibet_hermes import install_skill, install_mcp_config
  install_skill()
  install_mcp_config()
"""

from __future__ import annotations

import shutil
from pathlib import Path

# Skill source (bundled with this package)
SKILL_DIR = Path(__file__).parent / "skill"
HERMES_HOME = Path.home() / ".hermes"


def install_skill(hermes_home: Path | None = None) -> Path:
    """Install the tibet-trust skill into ~/.hermes/skills/tibet-trust/"""
    home = hermes_home or HERMES_HOME
    target = home / "skills" / "tibet-trust"
    target.mkdir(parents=True, exist_ok=True)

    # Copy SKILL.md
    src = SKILL_DIR / "SKILL.md"
    dst = target / "SKILL.md"
    shutil.copy2(src, dst)

    print(f"  Installed tibet-trust skill → {target}")
    return target


def install_mcp_config(
    hermes_home: Path | None = None,
    tibet_api: str = "http://localhost:8000",
    ains_api: str = "https://brein.jaspervandemeent.nl",
) -> Path:
    """Add TIBET MCP server config to ~/.hermes/config.yaml (non-destructive)."""
    home = hermes_home or HERMES_HOME
    config_path = home / "config.yaml"

    mcp_block = f"""
# ── TIBET Trust Layer (added by tibet-hermes) ──
# MCP server for provenance, identity, and .aint networking
mcp:
  servers:
    tibet:
      command: "tibet-ainternet-mcp"
      env:
        TIBET_API_URL: "{tibet_api}"
        AINS_API_URL: "{ains_api}"

# TIBET Memory Provider
memory:
  provider: tibet
  tibet:
    api_url: "{tibet_api}"
    ains_url: "{ains_api}"
    use_vault: false  # Set to true for Bifurcation-sealed memories
"""

    if config_path.exists():
        content = config_path.read_text()
        if "tibet" in content.lower():
            print(f"  TIBET config already present in {config_path}")
            return config_path
        # Append to existing config
        with open(config_path, "a") as f:
            f.write(mcp_block)
        print(f"  Appended TIBET config to {config_path}")
    else:
        home.mkdir(parents=True, exist_ok=True)
        config_path.write_text(mcp_block.lstrip())
        print(f"  Created {config_path} with TIBET config")

    return config_path


def install_memory_plugin(hermes_home: Path | None = None) -> Path:
    """Install TIBET memory provider plugin into ~/.hermes/plugins/memory/tibet/"""
    home = hermes_home or HERMES_HOME
    plugin_dir = home / "plugins" / "memory" / "tibet"
    plugin_dir.mkdir(parents=True, exist_ok=True)

    # Copy the provider module
    src = Path(__file__).parent / "memory_provider" / "provider.py"
    dst = plugin_dir / "provider.py"
    shutil.copy2(src, dst)

    # Create __init__.py for plugin discovery
    init = plugin_dir / "__init__.py"
    init.write_text(
        'from tibet_hermes.memory_provider.provider import TibetMemoryProvider\n'
        'Provider = TibetMemoryProvider\n'
    )

    print(f"  Installed TIBET memory provider → {plugin_dir}")
    return plugin_dir


def main():
    """CLI entry point: tibet-hermes-install"""
    print()
    print("tibet-hermes — Installing TIBET trust layer for Hermes Agent")
    print("=" * 60)
    print()

    install_skill()
    install_mcp_config()
    install_memory_plugin()

    print()
    print("Done! TIBET trust layer installed.")
    print()
    print("What's active:")
    print("  - tibet-trust skill (teaches Hermes when to use TIBET)")
    print("  - TIBET MCP server config (provenance, identity, messaging)")
    print("  - TIBET memory provider (sealed memories, verified recall)")
    print()
    print("Next steps:")
    print("  1. Start Hermes: hermes")
    print("  2. It will auto-discover the tibet-trust skill")
    print("  3. Every action gets a TIBET token")
    print("  4. Every memory is cryptographically sealed")
    print()
    print("Publish your skills to the AInternet:")
    print("  python -c 'import asyncio; from tibet_hermes import publish_skills; asyncio.run(publish_skills(\"your_name.aint\"))'")
    print()
    print("Identity is key. Every action, verified.")
    print()


if __name__ == "__main__":
    main()
