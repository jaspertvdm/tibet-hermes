"""Tests for tibet-hermes AINS skill discovery."""

import json
from pathlib import Path
from datetime import datetime, timezone

import httpx
import pytest

from tibet_hermes.discovery.ains_skills import (
    SkillEntry,
    SkillManifest,
    publish_skills,
    discover_skills,
)


class TestSkillEntry:
    def test_auto_timestamps(self):
        entry = SkillEntry(name="test", description="A test skill")
        assert entry.created != ""
        assert entry.updated != ""

    def test_preserves_explicit_timestamps(self):
        entry = SkillEntry(
            name="test",
            description="A test skill",
            created="2026-01-01T00:00:00",
            updated="2026-01-01T00:00:00",
        )
        assert entry.created == "2026-01-01T00:00:00"

    def test_default_version(self):
        entry = SkillEntry(name="x", description="y")
        assert entry.version == "0.1.0"


class TestSkillManifest:
    def test_add_skill_from_dir(self, tmp_path):
        skill_dir = tmp_path / "my-skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text(
            "---\nname: my-skill\ndescription: Test skill\n---\n\nBody here."
        )

        manifest = SkillManifest(agent="test.aint")
        entry = manifest.add_skill(skill_dir)

        assert entry is not None
        assert entry.name == "my-skill"
        assert entry.description == "Test skill"
        assert entry.content_hash.startswith("sha256:")
        assert len(manifest.skills) == 1

    def test_add_skill_no_frontmatter(self, tmp_path):
        skill_dir = tmp_path / "plain"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("Just a plain skill document.")

        manifest = SkillManifest(agent="test.aint")
        entry = manifest.add_skill(skill_dir)

        assert entry is not None
        assert entry.name == "plain"  # falls back to dir name

    def test_add_skill_missing_md(self, tmp_path):
        skill_dir = tmp_path / "empty"
        skill_dir.mkdir()

        manifest = SkillManifest(agent="test.aint")
        entry = manifest.add_skill(skill_dir)
        assert entry is None

    def test_add_skill_replaces_existing(self, tmp_path):
        skill_dir = tmp_path / "dupe"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("---\nname: dupe\ndescription: v1\n---\nBody.")

        manifest = SkillManifest(agent="test.aint")
        manifest.add_skill(skill_dir)
        assert len(manifest.skills) == 1

        (skill_dir / "SKILL.md").write_text("---\nname: dupe\ndescription: v2\n---\nUpdated.")
        manifest.add_skill(skill_dir)
        assert len(manifest.skills) == 1
        assert manifest.skills[0].description == "v2"

    def test_roundtrip_serialization(self):
        manifest = SkillManifest(
            agent="round.aint",
            skills=[SkillEntry(name="a", description="skill a")],
        )
        data = manifest.to_dict()
        json_str = manifest.to_json()

        restored = SkillManifest.from_dict(json.loads(json_str))
        assert restored.agent == "round.aint"
        assert len(restored.skills) == 1
        assert restored.skills[0].name == "a"

    def test_from_dict_empty_skills(self):
        manifest = SkillManifest.from_dict({"agent": "empty.aint"})
        assert manifest.agent == "empty.aint"
        assert len(manifest.skills) == 0


class TestPublishSkills:
    @pytest.mark.asyncio
    async def test_publish_empty_skills_dir(self, tmp_path):
        hermes_home = tmp_path / ".hermes"
        manifest = await publish_skills("test.aint", hermes_home=hermes_home)
        assert manifest.agent == "test.aint"
        assert len(manifest.skills) == 0

    @pytest.mark.asyncio
    @pytest.mark.httpx_mock(can_send_already_matched_responses=True)
    async def test_publish_with_skill(self, tmp_path, httpx_mock):
        hermes_home = tmp_path / ".hermes"
        skills_dir = hermes_home / "skills" / "my-skill"
        skills_dir.mkdir(parents=True)
        (skills_dir / "SKILL.md").write_text(
            "---\nname: my-skill\ndescription: Pub test\n---\nContent."
        )

        # Mock TIBET API responses (called twice: skill token + manifest token)
        httpx_mock.add_response(
            url="http://localhost:8000/api/tibet/create",
            json={"token_id": "tok_skill_123"},
        )

        manifest = await publish_skills("pub.aint", hermes_home=hermes_home)
        assert len(manifest.skills) == 1
        assert manifest.skills[0].tibet_token_id == "tok_skill_123"
        assert manifest.tibet_manifest_token == "tok_skill_123"

        # Manifest saved locally
        manifest_file = hermes_home / "tibet_skill_manifest.json"
        assert manifest_file.exists()

    @pytest.mark.asyncio
    @pytest.mark.httpx_mock(can_send_already_matched_responses=True)
    async def test_publish_handles_api_failure(self, tmp_path, httpx_mock):
        hermes_home = tmp_path / ".hermes"
        skills_dir = hermes_home / "skills" / "failskill"
        skills_dir.mkdir(parents=True)
        (skills_dir / "SKILL.md").write_text("Skill content.")

        httpx_mock.add_response(
            url="http://localhost:8000/api/tibet/create",
            status_code=500,
        )

        manifest = await publish_skills("fail.aint", hermes_home=hermes_home)
        assert len(manifest.skills) == 1
        assert manifest.skills[0].tibet_token_id is None


class TestDiscoverSkills:
    @pytest.mark.asyncio
    async def test_discover_unknown_agent(self, httpx_mock):
        httpx_mock.add_response(
            url="https://brein.jaspervandemeent.nl/api/ains/resolve/unknown",
            status_code=404,
        )
        result = await discover_skills("unknown.aint")
        assert result is None

    @pytest.mark.asyncio
    async def test_discover_agent_without_skills(self, httpx_mock):
        httpx_mock.add_response(
            url="https://brein.jaspervandemeent.nl/api/ains/resolve/basic",
            json={"capabilities": ["chat"], "skill_manifest": None},
        )
        result = await discover_skills("basic.aint")
        assert result is None

    @pytest.mark.asyncio
    async def test_discover_agent_with_manifest(self, httpx_mock):
        manifest_data = {
            "agent": "helper.aint",
            "skills": [
                {
                    "name": "tibet-trust",
                    "description": "Trust layer",
                    "version": "0.1.0",
                    "tibet_token_id": "tok_123",
                    "content_hash": "sha256:abc",
                    "created": "2026-04-18T00:00:00",
                    "updated": "2026-04-18T00:00:00",
                }
            ],
            "updated": "2026-04-18T00:00:00",
            "tibet_manifest_token": "tok_manifest",
        }

        httpx_mock.add_response(
            url="https://brein.jaspervandemeent.nl/api/ains/resolve/helper",
            json={
                "capabilities": ["skill_manifest"],
                "skill_manifest": manifest_data,
            },
        )
        httpx_mock.add_response(
            url="http://localhost:8000/api/tibet/verify/tok_manifest",
            json={"valid": True},
        )

        result = await discover_skills("helper.aint")
        assert result is not None
        assert result.agent == "helper.aint"
        assert len(result.skills) == 1
        assert result.skills[0].name == "tibet-trust"

    @pytest.mark.asyncio
    async def test_discover_rejects_invalid_manifest_token(self, httpx_mock):
        httpx_mock.add_response(
            url="https://brein.jaspervandemeent.nl/api/ains/resolve/evil",
            json={
                "capabilities": ["skill_manifest"],
                "skill_manifest": {
                    "agent": "evil.aint",
                    "skills": [],
                    "tibet_manifest_token": "tok_bad",
                },
            },
        )
        httpx_mock.add_response(
            url="http://localhost:8000/api/tibet/verify/tok_bad",
            json={"valid": False},
        )

        result = await discover_skills("evil.aint")
        assert result is None
