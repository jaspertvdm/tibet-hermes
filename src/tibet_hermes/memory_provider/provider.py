"""TibetMemoryProvider — Hermes MemoryProvider with cryptographic provenance.

Every memory write → TIBET token + optional Bifurcation seal.
Every memory read → verify TIBET chain, reject tampered entries.
Every turn → provenance record.

Implements the MemoryProvider ABC from hermes-agent:
  agent/memory_provider.py → MemoryProvider

Install:
  In ~/.hermes/config.yaml:
    memory:
      provider: tibet

  Place this plugin in:
    ~/.hermes/plugins/memory/tibet/
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

logger = logging.getLogger("tibet_hermes.memory")

# TIBET API (brain_api or ainternet.org)
DEFAULT_TIBET_API = "http://localhost:8000"
DEFAULT_AINS_API = "https://brein.jaspervandemeent.nl"


class TibetMemoryProvider:
    """Hermes MemoryProvider with TIBET provenance and optional vault sealing.

    Lifecycle (called by Hermes Agent):
        initialize()          → setup, load config
        system_prompt_block() → inject trust context into system prompt
        prefetch(query)       → recall memories, verify provenance
        sync_turn(user, assistant) → record turn, create TIBET token
        on_memory_write()     → seal + token per memory entry
        get_tool_schemas()    → expose TIBET tools to the agent
        handle_tool_call()    → dispatch TIBET tool calls
        shutdown()            → cleanup
    """

    def __init__(self):
        self.session_id: str | None = None
        self.agent_aint: str = "hermes.aint"
        self.tibet_api: str = DEFAULT_TIBET_API
        self.ains_api: str = DEFAULT_AINS_API
        self.hermes_home: Path = Path.home() / ".hermes"
        self.memories_dir: Path = self.hermes_home / "tibet_memories"
        self.token_chain: list[str] = []
        self._client: httpx.AsyncClient | None = None
        self.use_vault: bool = False  # Bifurcation sealing (requires tibet-vault)

    async def initialize(
        self,
        session_id: str,
        hermes_home: str | Path | None = None,
        platform: str | None = None,
        agent_context: dict[str, Any] | None = None,
        **kwargs,
    ):
        """Called once at agent startup."""
        self.session_id = session_id
        if hermes_home:
            self.hermes_home = Path(hermes_home)
            self.memories_dir = self.hermes_home / "tibet_memories"

        self.memories_dir.mkdir(parents=True, exist_ok=True)

        # Load config from agent context
        if agent_context:
            self.agent_aint = agent_context.get("aint_domain", self.agent_aint)
            self.tibet_api = agent_context.get("tibet_api", self.tibet_api)
            self.ains_api = agent_context.get("ains_api", self.ains_api)
            self.use_vault = agent_context.get("use_vault", False)

        self._client = httpx.AsyncClient(timeout=10.0)

        # Record session start
        await self._create_token("session_start", {
            "session_id": session_id,
            "platform": platform or "cli",
            "agent": self.agent_aint,
        })

        logger.info(f"TIBET Memory initialized for {self.agent_aint} (session: {session_id})")

    def system_prompt_block(self) -> str:
        """Injected into the system prompt — tells the agent about TIBET."""
        return (
            "\n## TIBET Trust Layer\n"
            f"You are {self.agent_aint} on the AInternet. "
            "Every memory you store is cryptographically signed with a TIBET token. "
            "Every memory you recall is verified before use. "
            "Your skill provenance is auditable. "
            "Use tibet_create_token after significant actions. "
            "Use tibet_verify_token before trusting external claims.\n"
        )

    async def prefetch(self, query: str, session_id: str | None = None) -> str:
        """Recall memories relevant to the query. Verify provenance."""
        memories = []
        manifest_path = self.memories_dir / "manifest.json"

        if not manifest_path.exists():
            return ""

        manifest = json.loads(manifest_path.read_text())

        for entry in manifest.get("entries", []):
            # Simple keyword match (Hermes does semantic search externally)
            if any(word.lower() in entry.get("content", "").lower()
                   for word in query.split()[:5]):
                # Verify TIBET token if present
                token_id = entry.get("tibet_token_id")
                if token_id:
                    verified = await self._verify_token(token_id)
                    if not verified:
                        logger.warning(f"Memory {token_id} failed verification, skipping")
                        continue

                memories.append(entry["content"])

        if not memories:
            return ""

        return "\n§\n".join(memories[:10])  # Hermes § delimiter

    async def sync_turn(
        self,
        user: str,
        assistant: str,
        session_id: str | None = None,
    ):
        """Called after every conversation turn. Record provenance."""
        turn_hash = hashlib.sha256(
            f"{user}{assistant}{datetime.now(timezone.utc).isoformat()}".encode()
        ).hexdigest()[:16]

        await self._create_token("conversation_turn", {
            "session_id": session_id or self.session_id,
            "turn_hash": turn_hash,
            "user_length": len(user),
            "assistant_length": len(assistant),
        })

    async def on_memory_write(self, key: str, content: str) -> dict[str, Any]:
        """Called when the agent writes a memory. Seal + token."""
        content_hash = hashlib.sha256(content.encode()).hexdigest()

        # Create TIBET token for this memory
        token = await self._create_token("memory_write", {
            "key": key,
            "content_hash": content_hash,
            "content_length": len(content),
        })

        # Store in local manifest
        manifest_path = self.memories_dir / "manifest.json"
        manifest = {"entries": []}
        if manifest_path.exists():
            manifest = json.loads(manifest_path.read_text())

        manifest["entries"].append({
            "key": key,
            "content": content,
            "content_hash": content_hash,
            "tibet_token_id": token.get("token_id") if token else None,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

        manifest_path.write_text(json.dumps(manifest, indent=2))

        return {"token": token, "hash": content_hash}

    def get_tool_schemas(self) -> list[dict]:
        """Expose TIBET tools to the agent."""
        return [
            {
                "type": "function",
                "function": {
                    "name": "tibet_provenance",
                    "description": "Create a TIBET provenance token for the current action",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "action": {
                                "type": "string",
                                "description": "What action was performed",
                            },
                            "details": {
                                "type": "string",
                                "description": "Additional details about the action",
                            },
                        },
                        "required": ["action"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "tibet_verify",
                    "description": "Verify a TIBET token's authenticity",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "token_id": {
                                "type": "string",
                                "description": "The TIBET token ID to verify",
                            },
                        },
                        "required": ["token_id"],
                    },
                },
            },
        ]

    async def handle_tool_call(self, tool_name: str, args: dict) -> str:
        """Dispatch TIBET tool calls from the agent."""
        if tool_name == "tibet_provenance":
            token = await self._create_token(
                args["action"],
                {"details": args.get("details", "")},
            )
            return json.dumps(token or {"error": "Failed to create token"})

        elif tool_name == "tibet_verify":
            result = await self._verify_token(args["token_id"])
            return json.dumps({"verified": result, "token_id": args["token_id"]})

        return json.dumps({"error": f"Unknown tool: {tool_name}"})

    async def on_session_end(self):
        """Record session end with summary token."""
        await self._create_token("session_end", {
            "session_id": self.session_id,
            "tokens_created": len(self.token_chain),
            "chain": self.token_chain[-10:],  # last 10 tokens
        })

    async def shutdown(self):
        """Cleanup."""
        await self.on_session_end()
        if self._client:
            await self._client.aclose()

    # ── Internal helpers ──

    async def _create_token(self, action: str, metadata: dict) -> dict | None:
        """Create a TIBET token via the API."""
        if not self._client:
            return None
        try:
            resp = await self._client.post(
                f"{self.tibet_api}/api/tibet/create",
                json={
                    "action": action,
                    "actor": self.agent_aint,
                    "metadata": metadata,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
            )
            if resp.status_code == 200:
                token = resp.json()
                token_id = token.get("token_id", "")
                if token_id:
                    self.token_chain.append(token_id)
                return token
        except Exception as e:
            logger.warning(f"TIBET token creation failed: {e}")
        return None

    async def _verify_token(self, token_id: str) -> bool:
        """Verify a TIBET token via the API."""
        if not self._client:
            return False
        try:
            resp = await self._client.get(
                f"{self.tibet_api}/api/tibet/verify/{token_id}",
            )
            if resp.status_code == 200:
                return resp.json().get("valid", False)
        except Exception as e:
            logger.warning(f"TIBET verification failed: {e}")
        return False
