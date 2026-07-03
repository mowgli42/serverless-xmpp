# Text Interface Design (TUI) — Following IxDF Principles

**Framework**: Textual (Python)  
**Target Users**: Power users, terminal/SSH environments, low-resource devices, keyboard-centric workflows.  
**Design Goals**: Efficient, calm, highly visible status, minimal cognitive load, full keyboard control.

## Overall Layout (IxDF: Visibility + Consistency)

```
┌──────────────────────────────────────────────────────────────┐
│ Header: [Service Status] [Your Presence] [Help: ?]          │
├──────────────────────┬───────────────────────────────────────┤
│ Contacts             │ Chat with Alice Example               │
│                      │                                       │
│ 🔍 Search...         │ [Online] Alice Example                │
│                      │                                       │
│ ★ Alice Example      │ 09:12  You: Hey, how's the garden?    │
│    alice@jabber...   │                                       │
│    [Online]          │ 09:14  Alice: It's coming along! 🌱   │
│                      │                                       │
│   Bob                │ > Type message and press Enter...     │
│   Carol              │                                       │
│                      │ [Send] [Attach]                       │
└──────────────────────┴───────────────────────────────────────┘
```

**Key IxDF Applications**:
- **Visibility of system status**: Header always shows connection state and your presence. Contact list shows live presence dots + last seen.
- **Match between system & real world**: Standard chat layout with bubbles (or simple left/right styling in terminal). Timestamps, sender names.
- **User control**: Easy search/filter, quick keyboard navigation (vim-style or arrows), `?` for help overlay.
- **Error prevention**: JID validation on add/edit. Clear "pending / failed" states for messages.

## Core Screens & Interactions

### 1. Contacts Screen (Default / Sidebar)
- **Search/Filter**: Instant fuzzy search on name + JID + tags. (Recognition over recall)
- **List Items**: Name (bold), JID (subtle), presence indicator (colored dot + text), unread count badge, tags.
- **Actions**:
  - `Enter` / `o` → Open chat
  - `a` → Add new contact (modal with form)
  - `e` → Edit selected
  - `d` / `Delete` → Remove (with confirmation)
- **Presence**: Real-time updates pushed from service. Green = online, yellow = away, gray = offline.

### 2. Chat Screen / Pane
- **Header**: Contact name + JID + current presence + connection transport indicator (e.g., "via jabber.example.com" or "Direct P2P").
- **Message History**: Scrollable, virtualized if possible. 
  - Outgoing: Right-aligned, different color/style, delivery status (✓ sent, ✓✓ delivered, pending spinner).
  - Incoming: Left-aligned, name + timestamp.
  - Timestamps on hover or always visible (configurable).
- **Composer**:
  - Single-line or growing input.
  - `Enter` = send (with modifier for newline if multi-line enabled).
  - Clear visual "Sending..." state on submit (optimistic UI + server confirmation).
  - Emoji picker or simple /commands later.
- **Feedback**:
  - Immediate local echo of sent message.
  - Real-time incoming messages appear without manual refresh.
  - Connection loss banner with reconnect button.

### 3. Global Elements
- **Command Palette** or footer shortcuts (inspired by Textual best practices).
- **Help Screen** (`?`): Context-sensitive or full list of keybindings.
- **Settings Modal**: Manage service connection, your presence, data directory, etc.
- **Notifications**: Subtle bell or flash for new messages when chat not focused (configurable, respect terminal capabilities).

## Keyboard-First Design (Efficiency + User Control)

| Key          | Action                          | IxDF Principle          |
|--------------|---------------------------------|-------------------------|
| `?`          | Toggle help                     | Recognition             |
| `Ctrl+K`     | Command palette / quick switch  | Flexibility & efficiency|
| `j` / `k`    | Navigate contacts or messages   | Keyboard efficiency     |
| `Enter`      | Open chat / Send message        | Clear affordance        |
| `Esc`        | Close pane / cancel             | User control & freedom  |
| `Ctrl+C`     | Quit gracefully                 | Safe exit               |
| `/`          | Focus search                    | Recognition             |

## Visual & Theming

- Use Textual's CSS-like styling.
- Calm, high-contrast palette suitable for long terminal sessions.
- Subtle colors for status (avoid red/green only — use shapes + color).
- Consistent spacing and alignment.

## Error & Edge Case Handling (Error Prevention + Recovery)

- Invalid JID on add → inline validation + helpful message.
- Connection drop → prominent but non-alarming banner + automatic retry with visible countdown.
- Message send failure → message stays in list with "Failed — tap to retry" affordance.
- Empty state: "No contacts yet. Press `a` to add one."

## Future Enhancements (Post-MVP)

- Split view for multiple chats
- Message search / filter within chat
- Typing indicators (when supported by transport)
- Theming engine

This design prioritizes **calm, efficient, keyboard-driven interaction** while making critical state (connection, presence, delivery) highly visible — core IxDF strengths for communication tools.