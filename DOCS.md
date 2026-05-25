# Curator — Documentation

---

## Installation

### Requirements

- Python 3.11 or newer
- pip

Check your version:
```bash
python3 --version
```

### Install — Linux / macOS / Windows

Download or clone the project, then from inside the `curator/` folder run:

```bash
python3 install.py
```

The installer:
1. Installs all dependencies (`typer`, `feedparser`, `textual`) using the exact Python you ran it with — so there is no version mismatch possible.
2. Writes a `curator` launcher to `~/.local/bin/` (Linux/macOS) or `%LOCALAPPDATA%\Programs\curator\` (Windows).
3. Tells you if you need to update your PATH.

**If `curator` is not found after installing**, add the bin directory to your PATH permanently.

Linux / macOS — add to `~/.bashrc` or `~/.zshrc`:
```bash
export PATH="$HOME/.local/bin:$PATH"
```
Then reload:
```bash
source ~/.bashrc
```

Windows — add `%LOCALAPPDATA%\Programs\curator` to PATH via:
System Properties → Advanced → Environment Variables → PATH → Edit.

### Verify

```bash
curator --help
```

---

## Project structure

```
curator/
├── install.py          ← run once to register the `curator` command
├── pyproject.toml      ← package metadata
└── curator/
    ├── __init__.py
    ├── main.py         ← CLI (all commands live here)
    ├── database.py     ← SQLite storage
    ├── extract.py      ← feed fetching and parsing
    └── tui.py          ← interactive terminal UI
```

The database is created automatically the first time you run any `curator` command.
It always lives in the same place regardless of which directory you are in:

| OS      | Location |
|---------|----------|
| Linux   | `~/.local/share/curator/curator.db` |
| macOS   | `~/Library/Application Support/curator/curator.db` |
| Windows | `%APPDATA%\curator\curator.db` |

---

## CLI reference

### `curator add-feed`

Add a feed.

```
curator add-feed <url> <category> [name] [--type TYPE]
```

| Argument | Required | Description |
|----------|----------|-------------|
| `url`      | yes | The feed URL |
| `category` | yes | Label used for grouping, e.g. `BLOGS` or `AI` |
| `name`     | no  | Display name (defaults to the URL if omitted) |
| `--type`   | no  | Feed type — see table below (default: `rss`) |

**Feed types**

| Type      | Use for |
|-----------|---------|
| `rss`     | Standard RSS/Atom — arXiv, most blogs, news sites (default) |
| `blog`    | Same as `rss` — just a label for your own clarity |
| `youtube` | YouTube channels — pass the channel URL, Curator converts it |
| `spotify` | Spotify podcast shows — pass the show URL |
| `podcast` | Any podcast with a direct RSS/Atom feed URL |

**Examples**

```bash
curator add-feed "https://rss.arxiv.org/rss/cs.LG" "AI" "ArXiv ML"
curator add-feed "https://www.chess.com/rss/news" "CHESS" "Chess.com News"
curator add-feed "https://www.youtube.com/channel/UCYO_jab_esuFRV4b17AJtAw" "MATHS" "3Blue1Brown" --type youtube
curator add-feed "https://feeds.simplecast.com/xyz" "PODCASTS" "My Podcast" --type podcast
```

---

### `curator remove-feed`

Remove a feed and delete every article that came from it.

```
curator remove-feed <url>
```

The URL must be the exact one you used when adding the feed. Check it with `curator list-feeds`.

```bash
curator remove-feed "https://rss.arxiv.org/rss/cs.LG"
```

---

### `curator list-feeds`

Print every feed with its name, category, type, and URL — one per line.

```bash
curator list-feeds
```

---

### `curator display-category`

List every category and its feeds, with enabled (✓) / disabled (✗) status.

```bash
curator display-category
```

---

### `curator fetch`

Fetch new articles from every enabled feed. Only content from the **past 2 weeks** is
kept — anything older is automatically deleted when this command runs.

```bash
curator fetch
```

Dismissed articles (via `mark-viewed`) will never reappear even if the feed still lists them.

---

### `curator latest`

Print the latest unread articles.

```bash
curator latest
```

Filter to one category:
```bash
curator latest --category AI
curator latest -c CHESS
```

---

### `curator mark-viewed`

Permanently dismiss an article. It is removed from the database and its URL is
blocklisted — it will not come back on future fetches.

```bash
curator mark-viewed "https://arxiv.org/abs/2312.00001"
```

---

### `curator search`

Search titles, summaries, tags, and source names. Prints matching title, URL, and category.

```bash
curator search "transformer"
curator search "chess opening"
```

---

### `curator ui`

Launch the interactive terminal UI.

```bash
curator ui
```

---

## Interactive UI

### Keyboard shortcuts

| Key     | Action |
|---------|--------|
| `f`     | Fetch new articles from all feeds |
| `a`     | Open "Add feed" form |
| `d`     | Delete the highlighted feed (and all its articles) |
| `/`     | Focus the search bar |
| `Esc`   | Clear search and return to full list |
| `l`     | Toggle log / articles pane |
| `Enter` | Open article detail (summary + URL) |
| `m`     | Mark article as viewed (from detail view) |
| `q`     | Quit |

### Navigation

- Use arrow keys or click to move through the feed list on the left.
- **★ All articles** shows everything.
- Selecting a **CATEGORY** header filters to that category.
- Selecting a specific feed shows only that feed's articles.
- The `+Add` and `-Del` buttons mirror the `a` / `d` keyboard shortcuts.

### Search

The search bar is always visible at the bottom. Click it or press `/` to focus it.
Results update live as you type — searching titles, summaries, categories, and source
names. Press `Esc` to clear and return to the full list.

### Log

Press `l` or trigger a fetch (`f`) to see the log pane, which shows fetch progress
and any feed errors. Press `l` again to return to articles.

---

## Finding RSS feeds

Most sites publish a feed — you just need the URL.

- **arXiv**: `https://rss.arxiv.org/rss/<subject>` — subject codes at [arxiv.org/list](https://arxiv.org/list)
- **YouTube**: use the channel URL with `--type youtube`, Curator handles the conversion
- **Blogs / news**: try appending `/rss`, `/feed`, `/atom.xml`, or `/rss.xml` to the domain
- **Podcasts**: check the show's website or search [podcastindex.org](https://podcastindex.org)
- **Reddit**: `https://www.reddit.com/r/SUBREDDIT/.rss`
- **GitHub releases**: `https://github.com/USER/REPO/releases.atom`
- **Hacker News**: `https://news.ycombinator.com/rss`


## How dismissed articles work

When you run `curator mark-viewed` (or press `m` in the UI):

1. The article is **deleted** from the database immediately.
2. Its URL is added to a permanent **blocklist** (`dismissed` table).

On every future fetch, blocked URLs are skipped before insertion — they will never
come back regardless of how many times you fetch.

---

## Uninstalling

```bash
# Remove the launcher
rm ~/.local/bin/curator                                  # Linux / macOS
# Windows: delete %LOCALAPPDATA%\Programs\curator\curator.cmd

# Remove the database (this deletes all your feeds and articles)
rm -rf ~/.local/share/curator                            # Linux
rm -rf ~/Library/Application\ Support/curator            # macOS
# Windows: delete %APPDATA%\curator
```