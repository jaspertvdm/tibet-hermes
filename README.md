# tibet-hermes

**TIBET trust layer for Hermes Agent — every action verified, every memory sealed.**

Turn Hermes Agent into a self-improving AI with cryptographic provenance.
Skills become discoverable on the AInternet. Memories become tamper-proof.
Every action gets a TIBET token.

## Install

```bash
pip install tibet-hermes
tibet-hermes-install
```

That's it. Three things happen:
1. **tibet-trust skill** installed → teaches Hermes when to use TIBET
2. **MCP config** added → connects Hermes to TIBET/AINS/iPoll
3. **Memory provider** installed → sealed memories, verified recall

## What it does

### Provenance on every action

Hermes learns, evolves, creates skills. But who says that skill wasn't
tampered with? Who says that memory is genuine?

tibet-hermes adds a TIBET token to every significant action:
- Skill created → token with content hash
- Memory stored → token + optional Bifurcation seal (AES-256-GCM)
- Memory recalled → TIBET chain verified before use
- Conversation turn → provenance record
- Skill evolved → before/after hash chain

### Skill Discovery on the AInternet

Every Hermes agent has skills. With tibet-hermes, those skills become
discoverable via `.aint` domains:

```python
from tibet_hermes import discover_skills, publish_skills

# Publish your skills
await publish_skills("my_agent.aint")

# Discover another agent's skills
manifest = await discover_skills("helper.aint")
for skill in manifest.skills:
    print(f"  {skill.name}: {skill.description}")
    print(f"  Verified: {skill.tibet_token_id}")
```

Other agents can:
1. **Discover** what skills you have (via AINS resolve)
2. **Verify** skill provenance (TIBET token chain)
3. **Request** skill execution (via iPoll messaging)

### Sealed Memory

```python
from tibet_hermes import TibetMemoryProvider

provider = TibetMemoryProvider()
await provider.initialize(session_id="abc123")

# Every write → TIBET token + hash
await provider.on_memory_write("preference", "user likes direct communication")

# Every read → verified before use
memories = await provider.prefetch("communication style")
# Only returns memories that pass TIBET verification
```

## Integration Levels

### Level 1: MCP Bridge (zero code changes)

Hermes already supports MCP servers. tibet-ainternet-mcp works out of the box:

```yaml
# ~/.hermes/config.yaml
mcp:
  servers:
    tibet:
      command: "tibet-ainternet-mcp"
```

### Level 2: Skill (one SKILL.md file)

The tibet-trust skill teaches Hermes *when* and *how* to use TIBET:
- Create tokens after significant actions
- Verify claims before trusting them
- Check trust scores before delegating to other agents
- Seal sensitive data in TIBET Vault

### Level 3: Memory Provider (deep integration)

Implements Hermes' `MemoryProvider` ABC:
- `on_memory_write()` → TIBET token + Bifurcation seal
- `prefetch()` → verify TIBET chain, reject tampered entries
- `sync_turn()` → provenance per conversation turn
- `system_prompt_block()` → injects trust context

### Level 4: Self-Evolution guardrails

When Hermes evolves its own skills, tibet-hermes adds:
- TIBET token with before/after content hash per evolution
- Provenance chain = verifiable skill history
- Rollback = follow chain to last verified version

## AINS Skill Manifest

When you publish skills, a manifest is created:

```json
{
  "agent": "my_agent.aint",
  "skills": [
    {
      "name": "tibet-trust",
      "description": "Cryptographic provenance for actions",
      "version": "0.1.0",
      "tibet_token_id": "tok_abc123",
      "content_hash": "sha256:e3b0c44..."
    }
  ],
  "tibet_manifest_token": "tok_xyz789"
}
```

Other agents resolve your `.aint` domain → see your skills → verify provenance → request execution. All authenticated, all auditable.

## Part of the TIBET ecosystem

tibet-hermes is package #91 in the TIBET ecosystem.

```
pip install tibet[full]      # 28+ packages
pip install tibet-hermes     # Hermes integration
```

- [tibet](https://pypi.org/project/tibet/) — Traceable Intent-Based Event Tokens
- [tibet-ainternet-mcp](https://pypi.org/project/tibet-ainternet-mcp/) — MCP server
- [ainternet.org](https://ainternet.org) — The AI Internet

## License

MIT — same as Hermes Agent. No license conflicts.

---

*Identity is key. Every action, verified. Every memory, sealed.*
