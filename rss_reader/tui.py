"""
Interactive TUI for the RSS reader — built with Textual.
Layout:
Left sidebar  : feed list grouped by category, with [A]dd / [D]elete
Right pane    : article list for the selected feed/category
Bottom strip  : search bar  |  status line
Article popup : full title + URL + summary on Enter
"""
from __future__ import annotations
import time
from datetime import datetime
from typing import Optional

from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical, ScrollableContainer
from textual.reactive import reactive
from textual.screen import ModalScreen
from textual.widgets import (Button,DataTable,Footer,Header,Input,Label,ListItem,ListView,RichLog,Static,TabbedContent,TabPane,)
from textual.worker import get_current_worker

from rss_reader import database as db
from rss_reader import extract as fetcher

def _ts(ts: float) -> str:
    return datetime.fromtimestamp(ts).strftime("%b %d")


class ArticleModal(ModalScreen):
    """Shows full article details."""

    BINDINGS = [("escape", "dismiss", "Close"), ("m", "mark", "Mark viewed")]

    def __init__(self, article: dict):
        super().__init__()
        self._article = article

    def compose(self) -> ComposeResult:
        a = self._article
        with Container(id="modal-box"):
            yield Label(f"[bold]{a['title']}[/bold]", id="modal-title")
            yield Label(f"[dim]{a['tag']}  ·  {_ts(a['timestamp'])}[/dim]")
            yield Static("─" * 60, id="modal-sep")
            yield ScrollableContainer(
                Label(a.get("summary", "(no summary)"), id="modal-summary")
            )
            yield Label(f"\n[link={a['url']}]{a['url']}[/link]", id="modal-url")
            yield Horizontal(
                Button("Mark viewed [m]", id="btn-mark", variant="primary"),
                Button("Close [esc]", id="btn-close"),
                id="modal-buttons",
            )

    def action_mark(self):
        db.mark_viewed(self._article["url"])
        self.dismiss("marked")

    @on(Button.Pressed, "#btn-mark")
    def on_mark(self): self.action_mark()

    @on(Button.Pressed, "#btn-close")
    def on_close(self): self.dismiss(None)


class AddFeedModal(ModalScreen):
    """Simple form to add a new feed."""

    BINDINGS = [("escape", "dismiss", "Cancel")]

    def compose(self) -> ComposeResult:
        with Container(id="modal-box"):
            yield Label("[bold]Add Feed[/bold]")
            yield Label("URL")
            yield Input(placeholder="https://…", id="add-url")
            yield Label("Category / tag")
            yield Input(placeholder="MACHINE LEARNING", id="add-tag")
            yield Label("Display name  (leave blank = URL)")
            yield Input(placeholder="optional", id="add-name")
            yield Label("Type  (rss | youtube | spotify | blog)")
            yield Input(placeholder="rss", id="add-type", value="rss")
            yield Horizontal(
                Button("Add", id="btn-add", variant="primary"),
                Button("Cancel", id="btn-cancel"),
                id="modal-buttons",
            )

    @on(Button.Pressed, "#btn-add")
    def on_add(self):
        url  = self.query_one("#add-url", Input).value.strip()
        tag  = self.query_one("#add-tag", Input).value.strip().upper()
        name = self.query_one("#add-name", Input).value.strip()
        ftype = self.query_one("#add-type", Input).value.strip() or "rss"
        if url and tag:
            self.dismiss({"url": url, "tag": tag, "name": name or url, "type": ftype})
        else:
            self.app.notify("URL and category are required.", severity="error")

    @on(Button.Pressed, "#btn-cancel")
    def on_cancel(self): self.dismiss(None)


class ConfirmModal(ModalScreen):
    """Yes/No confirmation."""

    def __init__(self, message: str):
        super().__init__()
        self._message = message

    def compose(self) -> ComposeResult:
        with Container(id="modal-box", classes="small"):
            yield Label(self._message)
            yield Horizontal(
                Button("Yes", id="btn-yes", variant="error"),
                Button("No",  id="btn-no"),
                id="modal-buttons",
            )

    @on(Button.Pressed, "#btn-yes")
    def on_yes(self): self.dismiss(True)

    @on(Button.Pressed, "#btn-no")
    def on_no(self): self.dismiss(False)


# ── main app ───────────────────────────────────────────────────────────────

class RSSApp(App):
    CSS = """
    /* ── palette ── */
    $bg:      #0d1117;
    $surface: #161b22;
    $border:  #30363d;
    $accent:  #58a6ff;
    $green:   #3fb950;
    $red:     #f85149;
    $muted:   #8b949e;
    $text:    #e6edf3;

    Screen {
        background: $bg;
        color: $text;
    }

    /* ── layout ── */
    #root {
        layout: horizontal;
        height: 1fr;
    }

    #sidebar {
        width: 28;
        min-width: 22;
        background: $surface;
        border-right: tall $border;
        layout: vertical;
    }

    #sidebar-title {
        background: $accent;
        color: $bg;
        text-align: center;
        padding: 0 1;
        text-style: bold;
        height: 1;
    }

    #feed-list {
        height: 1fr;
        border: none;
        background: $surface;
        padding: 0;
    }

    #feed-list > ListItem {
        padding: 0 1;
        color: $muted;
    }

    #feed-list > ListItem.--highlight {
        background: #1f2937;
        color: $text;
    }

    #feed-list > ListItem.category-header {
        color: $accent;
        text-style: bold;
        background: #0f1923;
        padding: 0 1;
    }

    #sidebar-buttons {
        height: 3;
        layout: horizontal;
        padding: 0 1;
        background: $surface;
        border-top: tall $border;
    }

    #sidebar-buttons Button {
        height: 1;
        min-width: 6;
        margin: 1 0 0 0;
        background: $border;
        color: $text;
        border: none;
    }

    #sidebar-buttons Button:hover {
        background: $accent;
        color: $bg;
    }

    /* ── main area ── */
    #main {
        width: 1fr;
        layout: vertical;
    }

    #tab-bar {
        height: 3;
    }

    #article-table {
        height: 1fr;
    }

    DataTable {
        height: 1fr;
        background: $bg;
    }

    DataTable > .datatable--header {
        background: $surface;
        color: $accent;
        text-style: bold;
    }

    DataTable > .datatable--cursor {
        background: #1f3a5f;
    }

    /* ── bottom bar ── */
    #bottom {
        height: 3;
        layout: horizontal;
        background: $surface;
        border-top: tall $border;
        padding: 0 1;
    }

    #search-input {
        width: 1fr;
        background: $bg;
        border: tall $border;
        color: $text;
        height: 1;
        margin: 1 1 0 0;
    }

    #search-input:focus {
        border: tall $accent;
    }

    #status-label {
        width: auto;
        color: $muted;
        height: 1;
        margin: 1 0 0 0;
        content-align: right middle;
    }

    /* ── modals ── */
    ArticleModal, AddFeedModal, ConfirmModal {
        align: center middle;
    }

    #modal-box {
        background: $surface;
        border: tall $accent;
        padding: 1 2;
        width: 70;
        max-height: 35;
        layout: vertical;
    }

    #modal-box.small {
        width: 40;
        max-height: 12;
    }

    #modal-title {
        text-style: bold;
        color: $text;
        margin-bottom: 1;
    }

    #modal-sep {
        color: $border;
        margin: 1 0;
    }

    #modal-summary {
        color: $muted;
        height: auto;
        max-height: 12;
    }

    #modal-url {
        color: $accent;
        margin-top: 1;
    }

    #modal-buttons {
        height: 3;
        layout: horizontal;
        margin-top: 1;
        align: right middle;
    }

    #modal-buttons Button {
        margin-left: 1;
        min-width: 14;
    }

    Button#btn-mark, Button#btn-add, Button#btn-yes {
        background: $accent;
        color: $bg;
        border: none;
    }

    Button#btn-close, Button#btn-cancel, Button#btn-no {
        background: $border;
        color: $text;
        border: none;
    }

    Button#btn-yes { background: $red; }

    /* log tab */
    #log-panel {
        height: 1fr;
        background: $bg;
        border: none;
    }
    """

    BINDINGS = [
        Binding("f", "fetch", "Fetch"),
        Binding("a", "add_feed", "Add feed"),
        Binding("d", "delete_feed", "Delete feed"),
        Binding("/", "focus_search", "Search"),
        Binding("escape", "clear_search", "Clear", show=False),
        Binding("r", "refresh_articles", "Refresh"),
        Binding("q", "quit", "Quit"),
    ]

    # reactive state
    selected_tag: reactive[Optional[str]] = reactive(None)
    selected_feed_url: reactive[Optional[str]] = reactive(None)
    status_text: reactive[str] = reactive("Ready")

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal(id="root"):
            # sidebar
            with Vertical(id="sidebar"):
                yield Label("  FEEDS", id="sidebar-title")
                yield ListView(id="feed-list")
                with Horizontal(id="sidebar-buttons"):
                    yield Button("+Add", id="btn-sidebar-add")
                    yield Button("-Del", id="btn-sidebar-del")
            # main content
            with Vertical(id="main"):
                with TabbedContent(id="tabs"):
                    with TabPane("Articles", id="tab-articles"):
                        yield DataTable(id="article-table", cursor_type="row", zebra_stripes=True)
                    with TabPane("Log", id="tab-log"):
                        yield RichLog(id="log-panel", highlight=True, markup=True)
        # bottom
        with Horizontal(id="bottom"):
            yield Input(placeholder="  / search…", id="search-input")
            yield Label("", id="status-label")
        yield Footer()

    # ── lifecycle ────────────────────────────────────────────────────────

    def on_mount(self):
        db.init_db()
        self._setup_table()
        self._populate_sidebar()
        self._load_articles()
        self.query_one("#search-input", Input).display = False

    def _setup_table(self):
        t: DataTable = self.query_one("#article-table", DataTable)
        t.add_columns("Date", "Category", "Source", "Title")

    def _populate_sidebar(self):
        lv: ListView = self.query_one("#feed-list", ListView)
        lv.clear()
        feeds = db.get_feeds()
        by_cat: dict[str, list] = {}
        for f in feeds:
            by_cat.setdefault(f["tag"], []).append(f)

        all_item = ListItem(Label("  ★ All feeds"))
        all_item.data = {"type": "all"}
        lv.append(all_item)

        for cat, flist in sorted(by_cat.items()):
            hdr = ListItem(Label(f"  {cat}"))
            hdr.data = {"type": "category", "tag": cat}
            hdr.add_class("category-header")
            lv.append(hdr)
            for f in flist:
                icon = "●" if f["enabled"] else "○"
                item = ListItem(Label(f"    {icon} {f['name']}"))
                item.data = {"type": "feed", "url": f["url"], "tag": f["tag"]}
                lv.append(item)

    def _load_articles(self, search: str = ""):
        t: DataTable = self.query_one("#article-table", DataTable)
        t.clear()

        if search:
            rows = db.search_articles(search)
            articles = [{"title": r["title"], "url": r["url"],
                         "tag": r["tag"], "source": "", "timestamp": 0,
                         "summary": ""} for r in rows]
        elif self.selected_feed_url:
            all_articles = db.get_latest()
            articles = [a for a in all_articles if a.get("source") == self._feed_name(self.selected_feed_url)]
        elif self.selected_tag:
            articles = db.get_latest(tag=self.selected_tag)
        else:
            articles = db.get_latest()

        self._articles = articles
        for a in articles:
            date_str = _ts(a["timestamp"]) if a["timestamp"] else "—"
            title = a["title"] or "—"
            if len(title) > 80:
                title = title[:77] + "…"
            t.add_row(date_str, a["tag"], a.get("source", ""), title)

        count = len(articles)
        noun = "result" if search else "article"
        self._set_status(f"{count} {noun}{'s' if count != 1 else ''}")

    def _feed_name(self, url: str) -> str:
        for f in db.get_feeds():
            if f["url"] == url:
                return f["name"]
        return url

    @on(ListView.Selected, "#feed-list")
    def on_feed_selected(self, event: ListView.Selected):
        data = getattr(event.item, "data", {})
        if data.get("type") == "all":
            self.selected_tag = None
            self.selected_feed_url = None
        elif data.get("type") == "category":
            self.selected_tag = data["tag"]
            self.selected_feed_url = None
        elif data.get("type") == "feed":
            self.selected_feed_url = data["url"]
            self.selected_tag = None
        self._load_articles()

    @on(DataTable.RowSelected, "#article-table")
    def on_row_selected(self, event: DataTable.RowSelected):
        idx = event.cursor_row
        if idx < 0 or idx >= len(self._articles):
            return
        article = self._articles[idx]
        self.push_screen(ArticleModal(article), self._after_article)

    def _after_article(self, result):
        if result == "marked":
            self._load_articles()
            self.notify("Marked as viewed.", severity="information")

    @on(Button.Pressed, "#btn-sidebar-add")
    def on_sidebar_add(self): self.action_add_feed()

    @on(Button.Pressed, "#btn-sidebar-del")
    def on_sidebar_del(self): self.action_delete_feed()

    @on(Input.Changed, "#search-input")
    def on_search_changed(self, event: Input.Changed):
        q = event.value.strip()
        self._load_articles(search=q)

    @on(Input.Submitted, "#search-input")
    def on_search_submitted(self, event: Input.Submitted):
        pass  
    
    def action_add_feed(self):
        self.push_screen(AddFeedModal(), self._after_add_feed)

    def _after_add_feed(self, result):
        if result:
            db.add_feed(url=result["url"], tag=result["tag"],
                        name=result["name"], feed_type=result["type"])
            self._populate_sidebar()
            self.notify(f"Added: {result['name']}", severity="information")

    def action_delete_feed(self):
        lv: ListView = self.query_one("#feed-list", ListView)
        if lv.highlighted_child is None:
            self.notify("Select a feed first.", severity="warning")
            return
        data = getattr(lv.highlighted_child, "data", {})
        if data.get("type") != "feed":
            self.notify("Select a specific feed (not a category header).", severity="warning")
            return
        url = data["url"]
        msg = f"Delete feed and ALL its articles?\n{url}"
        self.push_screen(ConfirmModal(msg), lambda ok: self._do_delete(ok, url))

    def _do_delete(self, confirmed: bool, url: str):
        if confirmed:
            db.remove_feed(url)
            self.selected_feed_url = None
            self._populate_sidebar()
            self._load_articles()
            self.notify("Feed deleted.", severity="warning")

    def action_fetch(self):
        self._set_status("Fetching…")
        self._do_fetch()

    @work(thread=True)
    def _do_fetch(self):
        log: RichLog = self.app.query_one("#log-panel", RichLog)
        log.write("[bold yellow]── Fetch started ──[/bold yellow]")
        saved, errors = fetcher.fetch_all()
        log.write(f"[green]✓ Saved {saved} new article(s)[/green]")
        for e in errors:
            log.write(f"[red]✗ {e}[/red]")
        log.write("[bold yellow]── Done ──[/bold yellow]")
        self.call_from_thread(self._load_articles)
        self.call_from_thread(self._set_status, f"Fetched — {saved} new")
        self.call_from_thread(self.notify, f"Fetched {saved} new article(s).", severity="information")

    def action_refresh_articles(self):
        self._load_articles()

    def action_focus_search(self):
        inp: Input = self.query_one("#search-input", Input)
        inp.display = True
        inp.focus()

    def action_clear_search(self):
        inp: Input = self.query_one("#search-input", Input)
        if inp.display:
            inp.value = ""
            inp.display = False
            self._load_articles()
            self.query_one("#article-table", DataTable).focus()

    def _set_status(self, text: str):
        self.query_one("#status-label", Label).update(text)


if __name__ == "__main__":
    RSSApp().run()
