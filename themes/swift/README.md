# Swift XMPP Military Command Center Themes

Prototype set of **6 dark themes** for the [Swift XMPP client](https://swift.im/) (Adium-style message view), designed with **IxDF / interaction design principles** for high-stakes military / C2 / command-center environments.

These themes live in this repo as client-side UI assets for improved message display and grouping when using the classic Swift desktop client alongside serverless-xmpp workflows.

## Design Goals (IxDF-informed)

- **Visibility of system status** — clear sender, timestamp, and consecutive-message grouping
- **Match to the real world** — tactical, restrained, professional aesthetic (no neon party UI)
- **Consistency & standards** — same layout language across the set; variants only change palette & density
- **Aesthetic and minimalist design** — low visual noise, high information density when needed
- **Error prevention / recognition** — high contrast ratios, strong differentiation of incoming vs outgoing
- **Flexibility** — tight NextContent templates so consecutive messages from the same sender collapse cleanly
- Accessibility-minded contrast and scannability for long watch-standing sessions

### Core Palette Language
| Role              | Typical Hex     | Notes                          |
|-------------------|-----------------|--------------------------------|
| Background        | `#0B0E14` / `#0A0F1A` | Deep navy-black               |
| Surface / bubble  | `#141B26` / `#1A2332` | Slightly elevated             |
| Primary text      | `#E6EDF5`       | Soft high-contrast white      |
| Secondary / time  | `#8B9BB4`       | Muted blue-gray               |
| Accent (info)     | `#00C2D8` / cyan | Active / system               |
| Accent (attention)| `#FFB000` / amber | Highlight / alert             |
| Accent (positive) | `#5C8A3A` / olive | Secure / friendly             |
| Border            | `#1E2A3A`       | Subtle separators             |

## Themes Included

1. **CommandCenter** — Balanced default. Cyan accents, clean bubbles, good everyday C2 use.
2. **NightOps** — Near-black, amber highlights. Lowest luminance for darkened rooms / NVG-friendly ambient.
3. **TacticalGreen** — Olive / drab green text & accents. Classic military terminal feel.
4. **HUD-Cyan** — Strong cyan / HUD aesthetic with subtle glow edges. High “situational awareness” feel.
5. **StealthDense** — Ultra-minimal, grayscale + single accent, tighter spacing for high message volume.
6. **C2-Amber** — Amber-forward status language. Good when operators need stronger visual “attention” cues.

## Installation (Swift Desktop)

Swift loads Adium-compatible themes from a path containing `Contents/Resources/`.

1. Copy a theme folder (e.g. `themes/swift/CommandCenter`) into Swift’s theme search path, **or**
2. Point Swift at the folder via its theme selection UI / preferences (exact location depends on version and OS).
3. Select the theme / variant inside Swift.

**Note:** These are prototypes. Test consecutive message grouping (`NextContent.html`) thoroughly.

## Screenshots

See [GALLERY.md](GALLERY.md) for live previews of all six themes with descriptions.

## Structure of each theme

```
ThemeName/
└── Contents/
    └── Resources/
        ├── main.css                 # Core styles
        ├── Template.html            # Page wrapper
        ├── Incoming/
        │   ├── Content.html
        │   └── NextContent.html
        ├── Outgoing/
        │   ├── Content.html
        │   └── NextContent.html
        └── Variants/                # Optional alternate CSS
```

## License

MIT — free to adapt for operational or personal use.
