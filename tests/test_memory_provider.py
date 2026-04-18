"""Tests for tibet-hermes TibetMemoryProvider."""

import json
from pathlib import Path

import pytest

from tibet_hermes.memory_provider.provider import TibetMemoryProvider


@pytest.fixture
def hermes_home(tmp_path):
    return tmp_path / ".hermes"


@pytest.fixture
def provider():
    return TibetMemoryProvider()


class TestInitialize:
    @pytest.mark.asyncio
    async def test_basic_init(self, provider, hermes_home, httpx_mock):
        httpx_mock.add_response(
            url="http://localhost:8000/api/tibet/create",
            json={"token_id": "tok_session_start"},
        )

        await provider.initialize(
            session_id="test-123",
            hermes_home=hermes_home,
        )

        assert provider.session_id == "test-123"
        assert provider.memories_dir.exists()
        assert len(provider.token_chain) == 1

    @pytest.mark.asyncio
    async def test_init_with_context(self, provider, hermes_home, httpx_mock):
        httpx_mock.add_response(
            url="http://custom:9000/api/tibet/create",
            json={"token_id": "tok_1"},
        )

        await provider.initialize(
            session_id="ctx-test",
            hermes_home=hermes_home,
            agent_context={
                "aint_domain": "custom.aint",
                "tibet_api": "http://custom:9000",
                "use_vault": True,
            },
        )

        assert provider.agent_aint == "custom.aint"
        assert provider.tibet_api == "http://custom:9000"
        assert provider.use_vault is True

    @pytest.mark.asyncio
    async def test_init_handles_api_down(self, provider, hermes_home, httpx_mock):
        httpx_mock.add_response(
            url="http://localhost:8000/api/tibet/create",
            status_code=500,
        )

        # Should not raise
        await provider.initialize(session_id="offline", hermes_home=hermes_home)
        assert provider.session_id == "offline"
        assert len(provider.token_chain) == 0


class TestSystemPrompt:
    def test_system_prompt_block(self, provider):
        provider.agent_aint = "mybot.aint"
        block = provider.system_prompt_block()
        assert "mybot.aint" in block
        assert "TIBET" in block
        assert "provenance" in block.lower()


class TestMemoryWrite:
    @pytest.mark.asyncio
    async def test_write_creates_manifest(self, provider, hermes_home, httpx_mock):
        httpx_mock.add_response(
            url="http://localhost:8000/api/tibet/create",
            json={"token_id": "tok_write"},
        )

        provider.memories_dir = hermes_home / "tibet_memories"
        provider.memories_dir.mkdir(parents=True)
        provider._client = __import__("httpx").AsyncClient(timeout=10.0)

        result = await provider.on_memory_write("greet", "Hello world!")

        assert result["hash"] is not None
        assert result["token"]["token_id"] == "tok_write"

        manifest_path = provider.memories_dir / "manifest.json"
        assert manifest_path.exists()
        manifest = json.loads(manifest_path.read_text())
        assert len(manifest["entries"]) == 1
        assert manifest["entries"][0]["key"] == "greet"
        assert manifest["entries"][0]["content"] == "Hello world!"

        await provider._client.aclose()

    @pytest.mark.asyncio
    @pytest.mark.httpx_mock(can_send_already_matched_responses=True)
    async def test_write_appends(self, provider, hermes_home, httpx_mock):
        httpx_mock.add_response(
            url="http://localhost:8000/api/tibet/create",
            json={"token_id": "tok_w"},
        )

        provider.memories_dir = hermes_home / "tibet_memories"
        provider.memories_dir.mkdir(parents=True)
        provider._client = __import__("httpx").AsyncClient(timeout=10.0)

        await provider.on_memory_write("key1", "value1")
        await provider.on_memory_write("key2", "value2")

        manifest = json.loads((provider.memories_dir / "manifest.json").read_text())
        assert len(manifest["entries"]) == 2

        await provider._client.aclose()


class TestPrefetch:
    @pytest.mark.asyncio
    async def test_prefetch_empty(self, provider, hermes_home):
        provider.memories_dir = hermes_home / "tibet_memories"
        provider.memories_dir.mkdir(parents=True)
        provider._client = __import__("httpx").AsyncClient(timeout=10.0)

        result = await provider.prefetch("anything")
        assert result == ""

        await provider._client.aclose()

    @pytest.mark.asyncio
    async def test_prefetch_matches_keyword(self, provider, hermes_home, httpx_mock):
        provider.memories_dir = hermes_home / "tibet_memories"
        provider.memories_dir.mkdir(parents=True)
        provider._client = __import__("httpx").AsyncClient(timeout=10.0)

        # Write manifest directly
        manifest = {
            "entries": [
                {
                    "key": "weather",
                    "content": "It is sunny today",
                    "tibet_token_id": "tok_v",
                },
                {
                    "key": "food",
                    "content": "I like pizza",
                    "tibet_token_id": "tok_v2",
                },
            ]
        }
        (provider.memories_dir / "manifest.json").write_text(json.dumps(manifest))

        httpx_mock.add_response(
            url="http://localhost:8000/api/tibet/verify/tok_v",
            json={"valid": True},
        )

        result = await provider.prefetch("sunny")
        assert "sunny" in result

        await provider._client.aclose()

    @pytest.mark.asyncio
    async def test_prefetch_skips_unverified(self, provider, hermes_home, httpx_mock):
        provider.memories_dir = hermes_home / "tibet_memories"
        provider.memories_dir.mkdir(parents=True)
        provider._client = __import__("httpx").AsyncClient(timeout=10.0)

        manifest = {
            "entries": [
                {"key": "bad", "content": "tampered data", "tibet_token_id": "tok_bad"},
            ]
        }
        (provider.memories_dir / "manifest.json").write_text(json.dumps(manifest))

        httpx_mock.add_response(
            url="http://localhost:8000/api/tibet/verify/tok_bad",
            json={"valid": False},
        )

        result = await provider.prefetch("tampered")
        assert result == ""

        await provider._client.aclose()


class TestToolSchemas:
    def test_exposes_two_tools(self, provider):
        schemas = provider.get_tool_schemas()
        assert len(schemas) == 2
        names = {s["function"]["name"] for s in schemas}
        assert "tibet_provenance" in names
        assert "tibet_verify" in names

    def test_tool_schema_structure(self, provider):
        schemas = provider.get_tool_schemas()
        for schema in schemas:
            assert schema["type"] == "function"
            assert "parameters" in schema["function"]
            assert "required" in schema["function"]["parameters"]


class TestHandleToolCall:
    @pytest.mark.asyncio
    async def test_provenance_tool(self, provider, httpx_mock):
        provider._client = __import__("httpx").AsyncClient(timeout=10.0)
        httpx_mock.add_response(
            url="http://localhost:8000/api/tibet/create",
            json={"token_id": "tok_prov"},
        )

        result = json.loads(
            await provider.handle_tool_call("tibet_provenance", {"action": "test_action"})
        )
        assert result["token_id"] == "tok_prov"

        await provider._client.aclose()

    @pytest.mark.asyncio
    async def test_verify_tool(self, provider, httpx_mock):
        provider._client = __import__("httpx").AsyncClient(timeout=10.0)
        httpx_mock.add_response(
            url="http://localhost:8000/api/tibet/verify/tok_check",
            json={"valid": True},
        )

        result = json.loads(
            await provider.handle_tool_call("tibet_verify", {"token_id": "tok_check"})
        )
        assert result["verified"] is True

        await provider._client.aclose()

    @pytest.mark.asyncio
    async def test_unknown_tool(self, provider):
        provider._client = __import__("httpx").AsyncClient(timeout=10.0)
        result = json.loads(
            await provider.handle_tool_call("nonexistent", {})
        )
        assert "error" in result
        await provider._client.aclose()


class TestSyncTurn:
    @pytest.mark.asyncio
    async def test_sync_creates_token(self, provider, httpx_mock):
        provider._client = __import__("httpx").AsyncClient(timeout=10.0)
        httpx_mock.add_response(
            url="http://localhost:8000/api/tibet/create",
            json={"token_id": "tok_turn"},
        )

        await provider.sync_turn("user said hi", "assistant replied")
        assert "tok_turn" in provider.token_chain

        await provider._client.aclose()
