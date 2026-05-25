# Curator

A personal terminal feed reader. Follow research papers, YouTube channels, blogs,
podcasts, or anything with an RSS/Atom feed — all in one place, from your terminal.

---

## Install

Requires Python 3.11+.

```bash
python3 install.py
```

Then add `~/.local/bin` to your PATH if prompted, and verify:

```bash
curator --help
```

Full installation guide, commands, and keyboard shortcuts → [DOCS.md](DOCS.md)

---

## Quick start

```bash
curator add-feed "https://rss.arxiv.org/rss/cs.LG" "AI" "ArXiv ML"
curator add-feed "https://www.chess.com/rss/news" "CHESS" "Chess.com"
curator fetch
curator ui
```

---

## License

MIT — see [LICENSE](LICENSE)