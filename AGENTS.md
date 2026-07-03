# AGENTS.md — Instructions for AI Coding Assistants (Cursor, Claude, etc.)

This file provides critical context and rules for any AI coding assistant working in this repository. **Read this file at the start of every session.**

## Core Philosophy

This is a **spec-driven project** using [OpenSpec](https://github.com/Fission-AI/OpenSpec).

- **Never write code before understanding the spec.**
- The source of truth for behavior is `openspec/changes/serverless-xmpp-p2p-chat-client/specs/spec.md` (requirements + Given/When/Then scenarios).
- Implementation must be traceable back to specific requirements.
- Prefer clarity, pragmatism, security, and local-first design over cleverness or premature optimization.

The user (PretzelerFL) is a pragmatic systems engineer who values:
- Extreme ownership
- Local control and privacy
- Clean separation of concerns
- Readable, maintainable code
- Tools that "just work" on modest hardware

## Mandatory Workflow

### 1. Before Any Implementation
- Read the relevant OpenSpec change folder:
  - **MVP / core client**: `openspec/changes/serverless-xmpp-p2p-chat-client/`
  - **XMPP resilience + address book sync**: `openspec/changes/enhance-xmpp-standards-resilience-addressbook-sync/`
- Within each folder read:
  - `proposal.md` — Why and scope
  - `design.md` — Architecture, tech choices, data models, API
  - `specs/spec.md` — Detailed behavioral requirements + scenarios (this is the contract)
  - `tasks.md` — Prioritized checklist (use this as your TODO list)

- Confirm which phase/task you are working on.
- If the task is ambiguous or a scenario is not covered, **stop and ask for clarification** or propose a spec update.

### 2. During Implementation
- Follow the task checklist in `tasks.md` sequentially.
- Write code that directly satisfies the Given/When/Then scenarios.
- Use type hints (where practical), clear naming, and docstrings on public functions/classes.
- Keep the Connection Service as the single source of truth for all XMPP logic, state, and persistence. UIs must remain thin.
- For UI work: Follow strong **Interaction Design (IxDF)** principles:
  - Provide immediate visual/feedback on every action (sending, connecting, errors).
  - Make presence and connection status highly visible.
  - Use consistent affordances (buttons, inputs, keyboard shortcuts).
  - Prevent errors where possible (e.g., validate JIDs before saving).
  - Support efficient keyboard navigation in the TUI.
  - In the web UI, follow modern chat conventions (message bubbles, timestamps, unread indicators, optimistic updates) while keeping the interface calm and focused.

### 3. After Changes
- Run linting/formatting: `ruff check --fix && ruff format`
- Manually or via test verify the relevant scenarios from the spec.
- Update `tasks.md` by marking completed items.
- If behavior diverged from the spec, update the spec (or justify why) before considering the task done.
- Commit with clear messages referencing the requirement or task (e.g., "feat: implement AddressBookManager per REQ-ADDR-001").

## Coding Standards

### Python (Connection Service + Text UI)
- Follow PEP 8 + modern practices.
- Prefer `asyncio` everywhere.
- Use `pydantic` or strict dataclasses for models where it adds clarity.
- Error handling: Never swallow exceptions silently. Surface meaningful messages to UIs via the API.
- Security: Assume all external input (including from address book) is untrusted until validated. Enforce TLS. Never log credentials.

### Web UI (Svelte)
- Use Svelte 5 runes/stores for reactive state.
- Keep components small and focused.
- All communication with the backend goes through a single `api.ts` client that handles reconnection and JSON-RPC.
- Follow the same IxDF principles as the TUI (clear feedback, visible status, efficient flows).

### General
- **No magic numbers or hardcoded strings** for user-facing text or important config.
- Prefer configuration and dependency injection over globals.
- Localhost-only by default for the API server.
- All persistent data lives under the user’s configured data directory (XDG-compliant where possible).

## OpenSpec & Spec Fidelity

- The `specs/spec.md` file uses a strict format. When adding or modifying requirements, maintain the `### Requirement:` + `#### Scenario:` structure with **GIVEN / WHEN / THEN / AND**.
- Use RFC 2119 keywords correctly (SHALL, MUST, SHOULD, MAY).
- If a new feature is requested that isn't in scope, create a new change proposal rather than hacking it into the current implementation.

## Security & Privacy Rules (Non-Negotiable)

- The Connection Service **MUST** bind its API only to `127.0.0.1` by default.
- All XMPP connections **MUST** use TLS 1.3 (or minimum configured version).
- Credentials are never stored in plain text in address book files.
- No network calls to any server except those explicitly configured by the user (XMPP servers or direct peer endpoints).
- No telemetry, analytics, or "phone home" behavior of any kind.
- When implementing direct P2P later: strict certificate/public-key pinning against address book entries.

## Testing Expectations

- Unit tests for core logic (AddressBookManager, Persistence, transport abstraction).
- Integration/smoke tests that exercise the happy-path scenarios from the spec (can use a local Prosody instance or public test XMPP accounts).
- Manual end-to-end validation using both UIs against the spec scenarios is required before marking a task complete.

## Interaction Design (IxDF) Guidance for Interfaces

When building or reviewing the Text TUI or Web UI:

- **Visibility of system status** — Connection state, presence, and message delivery status must be immediately visible.
- **Match between system and real world** — Use familiar chat metaphors (bubbles, "online" dots, typing indicators later).
- **User control and freedom** — Easy way to cancel sends, edit contacts, switch chats.
- **Consistency and standards** — Same keyboard shortcuts and visual language across TUI and Web where possible.
- **Error prevention & recovery** — Validate inputs early. Clear recovery paths for connection failures.
- **Recognition rather than recall** — Show contact names + JIDs. Recent chats easily accessible.
- **Flexibility and efficiency** — Keyboard power users in TUI; mouse + keyboard in web. Quick search/filter.
- **Aesthetic and minimalist design** — Chat is the focus. Avoid clutter. Calm color palette.

Reference: Interaction Design Foundation (IxDF) principles and chat UI patterns.

## What to Do If Stuck

1. Re-read the exact requirement/scenario in `specs/spec.md`.
2. Check `design.md` for intended architecture or data model.
3. Look for similar patterns already implemented.
4. Ask the user for clarification with a specific question referencing the spec section.
5. Never "just make it work" in a way that violates the spec or security rules.

## Project-Specific Context

- Owner: mowgli42
- Primary use case: Personal/trusted small-group communication with full local control.
- Hardware target: Runs well on modest machines (e.g., Ryzen 7 class, 16–32 GB RAM).
- Long-term vision: Extensible foundation for personal communication tooling (possible future voice, file sharing, agent integration).

---

**Follow these rules and the OpenSpec artifacts, and you will produce high-quality, aligned code that the user can trust.**

Welcome to the project. Let's build something excellent.