# Architecture diagrams

PlantUML sources and rendered PNGs for [architecture.md](../architecture.md).

| Source | Output |
|--------|--------|
| [src/architecture.puml](src/architecture.puml) | [architecture.png](architecture.png) |
| [src/startup.puml](src/startup.puml) | [startup.png](startup.png) |
| [src/client-connection.puml](src/client-connection.puml) | [client-connection.png](client-connection.png) |
| [src/shutdown.puml](src/shutdown.puml) | [shutdown.png](shutdown.png) |

Regenerate from the repo root:

```bash
pip install plantuml six
python scripts/render-diagrams.py
```

Edit the `.puml` files under `src/` — the markdown doc embeds the PNGs and links back to each source file.
