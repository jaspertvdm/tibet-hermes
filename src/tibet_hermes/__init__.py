"""tibet-hermes — TIBET trust layer for Hermes Agent.

Adds cryptographic provenance, sealed memory, and .aint skill discovery
to the Hermes Agent framework. Every skill, every memory, every action
gets a TIBET token. Skills become discoverable on the AInternet via AINS.

Three integration levels:
  1. MCP bridge (zero Hermes code changes)
  2. SKILL.md (teaches Hermes when to use TIBET)
  3. MemoryProvider plugin (sealed memories, verified recall)

Usage:
  pip install tibet-hermes
  tibet-hermes-install          # installs skill + MCP config into ~/.hermes/

  # Or programmatic:
  from tibet_hermes import TibetMemoryProvider, install_skill
"""

__version__ = "0.1.0"

from tibet_hermes.memory_provider.provider import TibetMemoryProvider
from tibet_hermes.discovery.ains_skills import SkillManifest, publish_skills, discover_skills
from tibet_hermes.installer import install_skill, install_mcp_config
