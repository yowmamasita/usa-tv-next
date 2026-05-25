# USA TV Next

Stremio addon serving free IPTV streams for US television channels.

## Structure

- `manifest.json` — Stremio addon manifest
- `catalog/tv/all.json` — Master catalog of all channels with metadata
- `catalog/tv/all/genre=*.json` — Per-genre catalog files
- `sources.yaml` — Harvester source definitions (GitHub repos, direct M3U URLs, websites, Telegram channels, paste sites)
- `harvester/` — Python tool that scrapes sources, deduplicates, and builds stream files
- `data/` — Harvested streams, test results, state files
- `public/` — Logo and background images

## Channels

169 channels with live streams across 10 genres:

| Genre | Count |
|-------|-------|
| Sports | 48 |
| Entertainment | 39 |
| Kids | 14 |
| News | 13 |
| Premium | 13 |
| Lifestyle | 13 |
| Documentaries | 11 |
| Music | 7 |
| Local | 6 |
| Latino | 5 |

Channels are hardcoded. Definitions live in `catalog/tv/all.json` (and per-genre files). Each channel has a Stremio meta object with `id`, `name`, `genres`, `poster`, and `posterShape`. Stream files are at `stream/tv/{channel_id}.json`. Adding or removing channels requires manually editing these catalog files.

## Hosting

Static files hosted on GitHub raw URLs from `yowmamasita/usa-tv-next` repo.

## Harvester

```bash
uv run python -m harvester          # Run full harvest
uv run python -m harvester test     # Test stream URLs
uv run python -m harvester report   # Generate report
```
