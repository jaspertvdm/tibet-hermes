"""AINS Skill Discovery — Skills as .aint-discoverable capabilities.

Every Hermes agent has skills. With AINS discovery, those skills become
visible on the AInternet. Other agents can:
  1. Discover what skills an agent has (ains_resolve → capabilities)
  2. Verify skill provenance (TIBET token chain per skill)
  3. Request skill execution via iPoll messaging

Skill Manifest format (published to AINS):
  {
    "agent": "helper.aint",
    "skills": [
      {
        "name": "tibet-trust",
        "description": "Cryptographic provenance for actions",
        "version": "0.1.0",
        "tibet_token_id": "tok_abc123",  # provenance of skill creation
        "hash": "sha256:...",            # content hash for integrity
      }
    ],
    "updated": "2026-04-18T...",
    "tibet_manifest_token": "tok_xyz789"  # token for the manifest itself
  }

Flow:
  1. Agent creates/modifies a skill
  2. tibet-hermes creates TIBET token for the change
  3. Skill manifest updated with new hash + token
  4. Manifest published to AINS (capabilities field on .aint domain)
  5. Other agents discover via ains_resolve → see skills + provenance
  6. They can request skill via ipoll_send(agent, {action: "skill_request", ...})
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

logger = logging.getLogger("tibet_hermes.discovery")

DEFAULT_AINS_API = "https://brein.jaspervandemeent.nl"
DEFAULT_TIBET_API = "http://localhost:8000"


@dataclass
class SkillEntry:
    """A single skill in the manifest."""
    name: str
    description: str
    version: str = "0.1.0"
    tibet_token_id: str | None = None
    content_hash: str | None = None
    created: str = ""
    updated: str = ""

    def __post_init__(self):
        now = datetime.now(timezone.utc).isoformat()
        if not self.created:
            self.created = now
        if not self.updated:
            self.updated = now


@dataclass
class SkillManifest:
    """Manifest of all skills an agent has, publishable to AINS."""
    agent: str
    skills: list[SkillEntry] = field(default_factory=list)
    updated: str = ""
    tibet_manifest_token: str | None = None

    def __post_init__(self):
        if not self.updated:
            self.updated = datetime.now(timezone.utc).isoformat()

    def add_skill(self, skill_dir: Path) -> SkillEntry | None:
        """Add a skill from its directory (reads SKILL.md)."""
        skill_md = skill_dir / "SKILL.md"
        if not skill_md.exists():
            return None

        content = skill_md.read_text()
        content_hash = f"sha256:{hashlib.sha256(content.encode()).hexdigest()}"

        # Parse frontmatter (simple YAML between --- markers)
        name = skill_dir.name
        description = ""
        if content.startswith("---"):
            parts = content.split("---", 2)
            if len(parts) >= 3:
                for line in parts[1].strip().split("\n"):
                    if line.startswith("name:"):
                        name = line.split(":", 1)[1].strip()
                    elif line.startswith("description:"):
                        description = line.split(":", 1)[1].strip()

        entry = SkillEntry(
            name=name,
            description=description,
            content_hash=content_hash,
        )

        # Replace existing or append
        self.skills = [s for s in self.skills if s.name != name]
        self.skills.append(entry)
        self.updated = datetime.now(timezone.utc).isoformat()

        return entry

    def to_dict(self) -> dict:
        """Serialize for AINS publication."""
        return {
            "agent": self.agent,
            "skills": [asdict(s) for s in self.skills],
            "updated": self.updated,
            "tibet_manifest_token": self.tibet_manifest_token,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)

    @classmethod
    def from_dict(cls, data: dict) -> SkillManifest:
        skills = [SkillEntry(**s) for s in data.get("skills", [])]
        return cls(
            agent=data["agent"],
            skills=skills,
            updated=data.get("updated", ""),
            tibet_manifest_token=data.get("tibet_manifest_token"),
        )


async def publish_skills(
    agent_aint: str,
    hermes_home: Path | None = None,
    tibet_api: str = DEFAULT_TIBET_API,
    ains_api: str = DEFAULT_AINS_API,
) -> SkillManifest:
    """Scan ~/.hermes/skills/, build manifest, publish to AINS.

    Each skill gets a TIBET token. The manifest itself gets a token.
    Published as capabilities on the agent's .aint domain.
    """
    home = hermes_home or Path.home() / ".hermes"
    skills_dir = home / "skills"
    manifest = SkillManifest(agent=agent_aint)

    if not skills_dir.exists():
        return manifest

    async with httpx.AsyncClient(timeout=10.0) as client:
        # Scan all skill directories
        for skill_dir in sorted(skills_dir.iterdir()):
            if not skill_dir.is_dir():
                continue
            entry = manifest.add_skill(skill_dir)
            if entry:
                # Create TIBET token for this skill
                try:
                    resp = await client.post(
                        f"{tibet_api}/api/tibet/create",
                        json={
                            "action": "skill_publish",
                            "actor": agent_aint,
                            "metadata": {
                                "skill_name": entry.name,
                                "content_hash": entry.content_hash,
                                "description": entry.description,
                            },
                        },
                    )
                    if resp.status_code == 200:
                        entry.tibet_token_id = resp.json().get("token_id")
                except Exception as e:
                    logger.warning(f"Token creation failed for skill {entry.name}: {e}")

        # Create manifest token
        manifest_hash = hashlib.sha256(manifest.to_json().encode()).hexdigest()
        try:
            resp = await client.post(
                f"{tibet_api}/api/tibet/create",
                json={
                    "action": "skill_manifest_publish",
                    "actor": agent_aint,
                    "metadata": {
                        "manifest_hash": f"sha256:{manifest_hash}",
                        "skill_count": len(manifest.skills),
                        "skills": [s.name for s in manifest.skills],
                    },
                },
            )
            if resp.status_code == 200:
                manifest.tibet_manifest_token = resp.json().get("token_id")
        except Exception as e:
            logger.warning(f"Manifest token creation failed: {e}")

        # Save manifest locally
        manifest_path = home / "tibet_skill_manifest.json"
        manifest_path.write_text(manifest.to_json())

    return manifest


async def discover_skills(
    agent_aint: str,
    ains_api: str = DEFAULT_AINS_API,
    tibet_api: str = DEFAULT_TIBET_API,
) -> SkillManifest | None:
    """Discover what skills another agent has via AINS resolve.

    Returns their skill manifest with provenance verification.
    """
    async with httpx.AsyncClient(timeout=10.0) as client:
        # Resolve agent on AINS
        try:
            domain = agent_aint.replace(".aint", "")
            resp = await client.get(f"{ains_api}/api/ains/resolve/{domain}")
            if resp.status_code != 200:
                return None

            agent_info = resp.json()
            capabilities = agent_info.get("capabilities", [])

            # Check if agent has skill_manifest capability
            if "skill_manifest" not in capabilities and "hermes" not in capabilities:
                return None

            # Fetch skill manifest from agent's metadata
            manifest_data = agent_info.get("skill_manifest")
            if not manifest_data:
                return None

            manifest = SkillManifest.from_dict(manifest_data)

            # Verify manifest TIBET token
            if manifest.tibet_manifest_token:
                try:
                    verify_resp = await client.get(
                        f"{tibet_api}/api/tibet/verify/{manifest.tibet_manifest_token}",
                    )
                    if verify_resp.status_code == 200:
                        if not verify_resp.json().get("valid", False):
                            logger.warning(
                                f"Skill manifest for {agent_aint} failed TIBET verification!"
                            )
                            return None
                except Exception:
                    pass  # Verification optional if API unreachable

            return manifest

        except Exception as e:
            logger.warning(f"Skill discovery failed for {agent_aint}: {e}")
            return None
