# USA TV Next

Stremio addon serving free IPTV streams for US television channels. Static JSON addon — no server, just files served from GitHub raw URLs.

## Quick Reference

```bash
uv run python -m harvester harvest          # Scrape all 167 sources for M3U streams
uv run python -m harvester test             # Test streams with ffprobe (DNS pre-filter + ffprobe)
uv run python -m harvester test --limit 100 # Test first N streams only
uv run python -m harvester report           # Generate report from test results
uv run python -m harvester run              # Harvest + test + report in sequence
uv run python -m harvester.inject           # Inject working streams into catalog channels
```

Run stream testing on macmini for speed: `ssh ben@macmini`. Requires `eval "$(/opt/homebrew/bin/brew shellenv zsh)"` before `uv` or `ffprobe`.

## Structure

```
manifest.json              — Stremio addon manifest (id: community.usa-tv-next)
catalog/tv/all.json        — Master catalog: 169 channels with metadata + streams
catalog/tv/all/genre=*.json — Per-genre catalog slices (13 genres)
meta/tv/ustv-*.json        — Individual channel meta files (190 files)
stream/tv/ustv-*.json      — Per-channel stream files (460 files, many empty placeholders)
sources.yaml               — 167 source definitions (GitHub repos, direct URLs, websites, Telegram, paste)
harvester/                 — Python scraping + testing + injection pipeline
data/                      — Harvested streams, test results, state (gitignored)
public/                    — Logo and background images
```

## Addon Data Flow

1. **Sources** (`sources.yaml`) define where to scrape M3U playlists
2. **Harvest** scrapes all sources, parses M3U, deduplicates by normalized URL
3. **Test** probes each stream URL: DNS resolve first (bulk dead domain elimination), then ffprobe
4. **Inject** matches working streams to existing catalog channels and writes them in
5. **Hosting**: GitHub raw URLs from `yowmamasita/usa-tv-next` repo serve the static JSON

## Channels

169 US TV channels across 13 genres. Channels are hardcoded — adding/removing requires editing catalog files.

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
| + Religious, Shopping, International |

Each channel is a Stremio meta object: `{id, name, genres, poster, posterShape, streams}`. Stream entries: `{url, behaviorHints: {notWebReady: true}, name: "FHD|HD|SD|Audio|[DEAD] HD", description: "HV:SOURCE_TAG"}`.

## Sources (`sources.yaml`)

167 sources across 5 types:

| Type | Count | Handler | Notes |
|------|-------|---------|-------|
| github | 72 | `sources/github.py` | Raw file fetch, tree API for globs, brute-force common M3U paths as fallback |
| direct | 56 | `sources/direct.py` | Direct M3U/M3U8 URLs |
| website | 30 | `sources/website.py` | HTML scraping for M3U links + Xtream Codes URLs |
| telegram | 8 | `sources/telegram.py` | Public Telegram channel scraping |
| paste | 1 | `sources/paste.py` | Paste site scraping |

GitHub source strategy: try literal paths first, then tree API (needs `GITHUB_TOKEN`, rate-limited at 60/hr unauthenticated), then brute-force ~55 common M3U filenames on both `main` and `master` branches.

## Harvester Architecture

```
harvester/
  cli.py        — Click CLI: harvest, test, report, run commands
  config.py     — Paths, timeouts (8s default), concurrency (harvest=10, test=50)
  models.py     — Pydantic models: SourceConfig, ParsedStream, StreamTestResult, CodecInfo
  parser.py     — M3U parser (EXTINF attrs, stream URLs, Xtream Codes detection)
  dedup.py      — URL normalization (strip tokens/sessions, normalize host/path) + dedup
  tester.py     — DNS pre-filter (200 concurrent resolves) + ffprobe testing (50 concurrent)
  inject.py     — Match working streams to catalog channels, update catalog/meta/genre files
  report.py     — Generate summary report from test results
  state.py      — Persist harvest/test state for resumable runs (atomic JSON writes)
  sources/
    base.py     — BaseSource ABC with fetch_url (retries, rate limit backoff)
    github.py   — GitHubSource: literal paths → tree API → brute-force common paths
    direct.py   — DirectSource: fetch + parse single M3U URL
    website.py  — WebsiteSource: scrape HTML for M3U links + Xtream URLs
    telegram.py — TelegramSource: scrape public Telegram channels
    paste.py    — PasteSource: scrape paste sites for M3U content
```

### Tester Pipeline

1. **DNS pre-filter**: Resolve unique hostnames (200 concurrent) → eliminate dead domains in bulk
2. **ffprobe**: Test surviving streams (50 concurrent, 8s timeout) → extract codecs, resolution, bitrate
3. Quality classification: FHD (≥1920w), HD (≥1280w), SD (≥720w), Audio (no video codec)

Optimal concurrency: 50 ffprobe processes. Higher (200+) overwhelms the system and kills accuracy.

### Inject Matching

`inject.py` matches harvested streams to catalog channels using:
- **Exact match**: normalized stream name == normalized channel name
- **Prefix match** (≥3 char names): stream name starts with channel name at word boundary, filtered by:
  - Non-US name suffixes (International, Italia, Indonesia, Finland, etc.)
  - Non-US URL patterns (qvcuk, tvkaista.net, etc.)
  - More-specific catalog channel dedup ("Fox" won't match "Fox News" if "Fox News" is its own channel)

### Dependencies

Python ≥3.10, managed with `uv`. Key deps: aiohttp, click, pydantic, pyyaml, rich. External: ffprobe (ffmpeg).

## Deployment

Push to `yowmamasita/usa-tv-next` on GitHub. Stremio clients fetch catalog/meta/stream JSON via raw.githubusercontent.com URLs. No build step needed.
