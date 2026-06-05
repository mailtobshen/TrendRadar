# TrendRadar (mailtobshen fork)

> This repository is a personal fork of [sansan0/TrendRadar](https://github.com/sansan0/TrendRadar). For the original project's feature overview, installation and configuration, please refer to the [upstream README](https://github.com/sansan0/TrendRadar/blob/master/README-EN.md). **This README only documents the differences introduced by this fork.**

## About this fork

| Item | Value |
|---|---|
| Upstream baseline | [v6.9.0](https://github.com/sansan0/TrendRadar) (commit `a583b2d`) |
| First migration | 2026-06-05 |
| Maintainer | mailtobshen |
| Goal | Layer personal customizations on top of upstream; maintained long-term |
| Plan | Periodically rebase upstream mainline; **no** PRs to upstream intended |

Detailed maintenance notes, credential handling, and sync workflow: see [FORK_NOTES.md](./FORK_NOTES.md).

---

## Changes relative to upstream

### 🎛️ WebUI configuration UI

- **WebUI preserved** (upstream v6.9.0 deleted `trendradar/webui/`; this fork restores and continues enhancing it)
- New **schedule system**: preset templates (always_on / morning_evening / office_hours / night_owl / custom) + crawl frequency
- New **RSS network test**: live reachability check for RSS feeds with status display
- New `report.max_news_per_source_per_keyword` field (max items per source per keyword)
- AI model dropdown: provider + model two-level linkage, supports 7 providers (openai / anthropic / gemini / deepseek / ollama / 2 custom)

### 🤖 AI module enhancements

- **provider / model field split** (replaces legacy `ai.model=provider/model` format)
- AIClient / AITester split with multi-provider support
- ModelCatalog module: LiteLLM catalog + custom model merge + live provider API refresh
- AI test-connection endpoint (`POST /api/ai/test`)
- **API key injected via environment variable** (not in `config.yaml`); see [docs/ai-env-vars.md](./docs/ai-env-vars.md)

### 🛠️ CLI data export subcommand

New `python -m trendradar export` subcommand:

```bash
python -m trendradar export --source hotlist --format json --pretty
python -m trendradar export --source rss --per-source-limit 5 --limit 100
python -m trendradar export --source ai --limit 50 --output ai_report.json
python -m trendradar export --source all --format json --pretty > all.json
```

Supports hotlist / rss / ai / all data sources and text / json output formats.

### 📡 RSS source expansion

10 new RSS sources added in `config/config.yaml`:

- **AI / Tech**: Github, Huggingface, AI-Era (新智元)
- **International media**: Reuters, DeutscheWelle, RFI (Radio France Internationale)
- **Chinese-language media**: CNA (Central News Agency), The Economist, Liberty Times (自由时报), Lianhe Zaobao (联合早报)

Plus restored `ruanyifeng` (atom.xml, default `enabled: false`). `display.regions.standalone: true` enables a standalone RSS section in reports.

### 🔒 Security / credentials

- **`expected_domain` validation** for 11 hotlist platforms (upstream v6.9.0 feature, enabled in this fork)
- **CDN multi-source fallback** (GitHub raw → jsdelivr fastly → jsdelivr cdn → gcore)
- **Mandatory API-key desensitization**: committed config holds the `YOUR_API_KEY_HERE` placeholder; real keys are injected via the `AI_API_KEY` environment variable
- WebUI-overwrite regression fix for `frequency_words.txt` (uses upstream's full version instead of the slimmed-down form)

### 📨 Reports / notifications

- HTML report: new **Markdown export** button (upstream v6.7.0 feature)
- HTML report / email respect `display.regions` switches (can disable standalone / ai_analysis sections)
- HTML report dark mode / search box / floating action buttons / wide mode (upstream v6.8.0 features)

### 🔧 Infrastructure

- `.gitignore` excludes runtime database files (`ruvector.db` / `*.rvf` / `*.rvf.lock`) so long-running processes don't pollute `git status`
- Comprehensive fork-maintenance docs ([FORK_NOTES.md](./FORK_NOTES.md)) and credential-injection docs ([docs/ai-env-vars.md](./docs/ai-env-vars.md))

---

## Syncing upstream

Weekly automatic monitoring of upstream updates (local cron reminder). When a rebase is needed:

```bash
git fetch upstream
git rebase upstream/master
# For conflict resolution, refer to docs/superpowers/specs/2026-06-04-trendradar-fork-migration-design.md §6.2
git push origin master --force-with-lease
```

High-risk conflict files: `config/config.yaml` / `trendradar/__main__.py` / `trendradar/report/html.py` — typically resolved with the "local-first + add upstream fixes later" strategy.

---

## Acknowledgements

- [sansan0/TrendRadar](https://github.com/sansan0/TrendRadar) — original project author and all [contributors](https://github.com/sansan0/TrendRadar/graphs/contributors)
- Migration design and implementation plan: see `docs/superpowers/specs/` and `docs/superpowers/plans/`

## License

This fork, like upstream, is licensed under [GPL-3.0](./LICENSE).
