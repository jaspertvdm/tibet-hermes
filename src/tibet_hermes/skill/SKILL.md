---
name: tibet-trust
description: Cryptographic provenance and identity verification for every significant action. Sealed memory, audit trails, and .aint agent discovery.
---

# TIBET Trust Protocol

You have access to the TIBET ecosystem for cryptographic provenance and identity.
Use these capabilities to make your actions verifiable, your memory tamper-proof,
and your identity discoverable.

## When to create TIBET tokens

Create a TIBET token (`tibet_create_token`) after:
- Completing a task that changes state (file edits, deployments, config changes)
- Making a decision that affects the user (recommendations, approvals, rejections)
- Learning something new (skill creation, memory updates)
- Receiving or sending messages to other agents (`ipoll_send` / `ipoll_receive`)

## When to verify

Use `tibet_verify_token` before trusting:
- Claims from other agents or external sources
- Memory entries that seem inconsistent
- Skills that were auto-evolved (check the provenance chain)
- Any data that arrived via network

## Identity

You have an IDD (Individual Device Derivate) on the AInternet — your `.aint` domain.
- Use `ains_whoami` to confirm your identity
- Use `ains_resolve` to look up other agents before interacting
- Use `ipoll_send` to message other agents on the network
- Use `ipoll_receive` to check your inbox

## Sealed Memory

When storing sensitive information:
- Use `tibet_vault_create` to seal data with AES-256-GCM encryption
- Use `tibet_vault_get` to retrieve and verify sealed data
- Every vault entry gets a TIBET token — tamper-proof provenance

## Skill Publishing

When you create or improve a skill:
1. Create a TIBET token recording the skill creation/modification
2. The token captures: who created it, when, what changed, and why
3. Published skills carry their provenance chain — other agents can verify origin

## Trust Scoring

Before executing actions requested by other agents:
- Check their trust score via `tibet_get_trust`
- Agents with trust < 0.5 require user confirmation
- Financial or destructive actions require trust > 0.8

## Example Flows

### Task completion with provenance
```
1. Complete the task
2. tibet_create_token(action="task_complete", details="deployed v2.1")
3. Report to user with token ID for verification
```

### Cross-agent collaboration
```
1. ains_resolve("collaborator.aint")  — verify they exist
2. tibet_get_trust("collaborator")     — check trust score
3. ipoll_send("collaborator.aint", message, type="TASK")
4. tibet_create_token(action="delegation", to="collaborator.aint")
```

### Skill evolution with audit
```
1. Identify skill improvement
2. tibet_create_token(action="skill_before", skill_hash=sha256(old_content))
3. Modify the skill
4. tibet_create_token(action="skill_after", skill_hash=sha256(new_content))
5. Chain links: before → after = verifiable evolution history
```
