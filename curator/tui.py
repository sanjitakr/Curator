"""
Curator — interactive terminal UI
"""
from __future__ import annotations

import re
from datetime import datetime
from typing import Optional

from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, ScrollableContainer, Vertical
from textual.screen import ModalScreen
from textual.widgets import (
    Button, DataTable, Footer, Header,
    Input, Label, ListItem, ListView, RichLog, Static,
)

from curator import database as db
from curator import extract as fetcher


# ── helpers ────────────────────────────────────────────────────────────────

def _fmt_date(ts: float) -> str:
    if not ts:
        return "—"
    return datetime.fromtimestamp(ts).strftime("%b %d")


def _strip_markup(text: str) -> str:
    """Remove [ ] characters that break Textual's markup parser."""
    return text.replace("[", "(").replace("]", ")")


def _strip_html(text: str) -> str:
    """Remove HTML tags from feed summaries."""
    return re.sub(r"<[^>]+>", "", text).strip()


# ── Article detail modal ───────────────────────────────────────────────────

class ArticleModal(ModalScreen):
    BINDINGS = [
        Binding("escape", "dismiss_modal", "Close"),
        Binding("m",      "mark_viewed",   "Mark viewed"),
    ]

    def __init__(self, article: dict):
        super().__init__()
        self._article = article

    def compose(self) -> ComposeResult:
        a = self._article
        # Fixed layout: header + meta + rule + scrollable summary + url + buttons
        # Buttons are OUTSIDE the scroll area so they're always visible
        with Container(id="modal"):
            yield Label("ARTICLE", id="modal-hdr")
            yield Static(_strip_markup(a.get("title", "") or "—"), id="modal-title")
            yield Static(
                f"{a.get('tag', '')}   {a.get('source', '')}   {_fmt_date(a.get('timestamp', 0))}",
                id="modal-meta",
            )
            yield Static("─" * 60, id="modal-rule")
            with ScrollableContainer(id="modal-scroll"):
                yield Static("", id="modal-body")
            yield Static(a.get("url", ""), id="modal-url")
            yield Horizontal(
                Button("Mark viewed  [m]", id="btn-mark", variant="primary"),
                Button("Close  [esc]",     id="btn-close"),
                id="modal-btns",
            )

    def on_mount(self):
        summary = _strip_html(self._article.get("summary", ""))
        self.query_one("#modal-body", Static).update(
            _strip_markup(summary) or "(no summary available)"
        )

    def action_dismiss_modal(self):
        self.dismiss(None)

    def action_mark_viewed(self):
        db.mark_viewed(self._article["url"])
        self.dismiss("marked")

    @on(Button.Pressed, "#btn-mark")
    def _on_mark(self): self.action_mark_viewed()

    @on(Button.Pressed, "#btn-close")
    def _on_close(self): self.dismiss(None)


# ── Add feed modal ─────────────────────────────────────────────────────────

class AddFeedModal(ModalScreen):
    BINDINGS = [Binding("escape", "dismiss_modal", "Cancel")]

    def compose(self) -> ComposeResult:
        with Container(id="modal"):
            yield Label("ADD FEED", id="modal-hdr")
            yield Label("URL  *")
            yield Input(placeholder="https://…", id="f-url")
            yield Label("Category  *")
            yield Input(placeholder="e.g. CHESS  /  AI  /  SCIENCE", id="f-tag")
            yield Label("Display name  (optional — leave blank to use URL)")
            yield Input(placeholder="My Feed", id="f-name")
            yield Label("Type  (rss · youtube · spotify · blog · podcast)")
            yield Input(value="rss", id="f-type")
            yield Horizontal(
                Button("Add feed", id="btn-add", variant="primary"),
                Button("Cancel",   id="btn-cancel"),
                id="modal-btns",
            )

    def action_dismiss_modal(self): self.dismiss(None)

    @on(Button.Pressed, "#btn-add")
    def _on_add(self):
        url   = self.query_one("#f-url",  Input).value.strip()
        tag   = self.query_one("#f-tag",  Input).value.strip().upper()
        name  = self.query_one("#f-name", Input).value.strip()
        ftype = self.query_one("#f-type", Input).value.strip() or "rss"
        if not url or not tag:
            self.notify("URL and category are required.", severity="error")
            return
        self.dismiss({"url": url, "tag": tag, "name": name or url, "type": ftype})

    @on(Button.Pressed, "#btn-cancel")
    def _on_cancel(self): self.dismiss(None)


# ── Confirm modal ──────────────────────────────────────────────────────────

class ConfirmModal(ModalScreen):
    def __init__(self, message: str):
        super().__init__()
        self._message = message

    def compose(self) -> ComposeResult:
        with Container(id="modal", classes="narrow"):
            yield Static(self._message, id="modal-confirm-msg")
            yield Horizontal(
                Button("Yes, delete", id="btn-yes", variant="error"),
                Button("Cancel",      id="btn-no"),
                id="modal-btns",
            )

    @on(Button.Pressed, "#btn-yes")
    def _on_yes(self): self.dismiss(True)

    @on(Button.Pressed, "#btn-no")
    def _on_no(self):  self.dismiss(False)


# ── Main app ───────────────────────────────────────────────────────────────

class CuratorApp(App):

    TITLE = "Curator"

    CSS = """
    Screen { background: #141317; color: #d4cfa8; }

    /* ── layout ── */
    #root  { layout: horizontal; height: 1fr; }
    #left  { width: 26; min-width: 20; layout: vertical; background: #1d1b21; border-right: tall #3c3840; }
    #right { width: 1fr; layout: vertical; }

    /* ── sidebar ── */
    #app-title {
        height: 1; background: #61fa46; color: #141317;
        text-style: bold; text-align: center; padding: 0 1;
    }
    #feed-list { height: 1fr; border: none; background: #1d1b21; }
    #feed-list > ListItem             { padding: 0 1; color: #a89980; }
    #feed-list > ListItem.--highlight { background: #2a2730; color: #fff7cc; }
    #feed-list > ListItem.cat-hdr     { color: #b8fa70; text-style: bold; background: #141317; }
    #sidebar-btns {
        height: 3; layout: horizontal; padding: 0 1;
        background: #1d1b21; border-top: tall #3c3840;
    }
    #sidebar-btns Button {
        height: 1; margin: 1 1 0 0; min-width: 9;
        background: #2a2730; color: #d4cfa8; border: none;
    }
    #sidebar-btns Button:hover { background: #61fa46; color: #141317; }

    /* ── articles / log pane ── */
    #pane-label {
        height: 1; background: #1d1b21; color: #b8fa70;
        text-style: bold; padding: 0 1; border-bottom: tall #3c3840;
    }
    DataTable { height: 1fr; background: #141317; }
    DataTable > .datatable--header { background: #1d1b21; color: #b8fa70; text-style: bold; }
    DataTable > .datatable--cursor { background: #2a2730; }
    DataTable > .datatable--hover  { background: #221f27; }
    #log { height: 1fr; background: #141317; border: none; display: none; }

    /* ── bottom bar ── */
    #bottom {
        height: 2; layout: horizontal; background: #1d1b21;
        border-top: solid #3c3840; padding: 0 1;
    }
    #search {
        width: 1fr; height: 1; margin: 0;
        background: #1d1b21; color: #d4cfa8;
        border: none;
    }
    #search:focus { background: #2a2730; }
    #search > .input--placeholder { color: #504d54; }
    #status { color: #a89980; height: 1; width: 18; content-align: right middle; }

    /* ── modals ── */
    ArticleModal, AddFeedModal, ConfirmModal { align: center middle; }

    #modal {
        background: #1d1b21; border: tall #61fa46;
        padding: 1 2; width: 74; height: auto; max-height: 38;
        layout: vertical;
    }
    #modal.narrow { width: 46; max-height: 12; }

    #modal-hdr          { background: #61fa46; color: #141317; text-style: bold; height: 1; padding: 0 1; margin-bottom: 1; }
    #modal-title        { color: #fff7cc; text-style: bold; margin-bottom: 0; }
    #modal-meta         { color: #a89980; margin-bottom: 1; }
    #modal-rule         { color: #3c3840; margin-bottom: 1; }
    #modal-scroll       { height: 10; border: none; background: #141317; margin-bottom: 1; }
    #modal-body         { color: #d4cfa8; padding: 0 1; }
    #modal-url          { color: #61fa46; margin-bottom: 1; }
    #modal-confirm-msg  { color: #d4cfa8; margin-bottom: 1; }

    #modal-btns         { height: 3; layout: horizontal; align: right middle; }
    #modal-btns Button  { margin-left: 1; min-width: 18; border: none; }

    Button#btn-mark   { background: #61fa46; color: #141317; }
    Button#btn-add    { background: #61fa46; color: #141317; }
    Button#btn-yes    { background: #fa4646; color: #fafdff; }
    Button#btn-close  { background: #2a2730; color: #d4cfa8; }
    Button#btn-cancel { background: #2a2730; color: #d4cfa8; }
    Button#btn-no     { background: #2a2730; color: #d4cfa8; }

    Label { margin-bottom: 0; }
    Input {
        margin-bottom: 1; background: #141317;
        color: #d4cfa8; border: tall #3c3840;
    }
    Input:focus { border: tall #61fa46; }
    Input > .input--placeholder { color: #504d54; }
    """

    BINDINGS = [
        Binding("f",      "fetch",        "Fetch"),
        Binding("a",      "add_feed",     "Add"),
        Binding("d",      "delete_feed",  "Delete"),
        Binding("/",      "open_search",  "Search"),
        Binding("escape", "close_search", "Clear",   show=False),
        Binding("l",      "toggle_log",   "Log"),
        Binding("q",      "quit",         "Quit"),
    ]

    def __init__(self):
        super().__init__()
        self._articles:        list[dict] = []
        self._selected_tag:    Optional[str] = None
        self._selected_source: Optional[str] = None
        self._log_visible:     bool = False

    # ── compose ───────────────────────────────────────────────────────────

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal(id="root"):
            with Vertical(id="left"):
                yield Label("  CURATOR", id="app-title")
                yield ListView(id="feed-list")
                with Horizontal(id="sidebar-btns"):
                    yield Button("+Add", id="btn-add-feed")
                    yield Button("-Del", id="btn-del-feed")
            with Vertical(id="right"):
                yield Label("  ARTICLES  ·  L for log", id="pane-label")
                yield DataTable(id="table", cursor_type="row", zebra_stripes=True)
                yield RichLog(id="log", highlight=False, markup=False)
        with Horizontal(id="bottom"):
            yield Input(placeholder="  search articles…", id="search")
            yield Label("", id="status")
        yield Footer()

    def on_mount(self):
        db.init_db()
        t = self.query_one("#table", DataTable)
        t.add_columns("Date", "Category", "Source", "Title")
        self._reload_sidebar()
        self._reload_articles()

    # ── sidebar ───────────────────────────────────────────────────────────

    def _reload_sidebar(self):
        lv = self.query_one("#feed-list", ListView)
        lv.clear()

        all_li = ListItem(Label("  ★  All articles"))
        all_li.data = {"type": "all"}
        lv.append(all_li)

        by_cat: dict[str, list] = {}
        for f in db.get_feeds():
            by_cat.setdefault(f["tag"], []).append(f)

        for cat, feeds in sorted(by_cat.items()):
            hdr = ListItem(Label(f"  {cat}"))
            hdr.data = {"type": "cat", "tag": cat}
            hdr.add_class("cat-hdr")
            lv.append(hdr)
            for f in feeds:
                dot  = "●" if f["enabled"] else "○"
                item = ListItem(Label(f"    {dot} {f['name']}"))
                item.data = {"type": "feed", "url": f["url"],
                             "name": f["name"], "tag": f["tag"]}
                lv.append(item)

    # ── articles ──────────────────────────────────────────────────────────

    def _reload_articles(self, search: str = ""):
        t = self.query_one("#table", DataTable)
        t.clear()

        if search:
            rows = db.search_articles(search)
            self._articles = [
                {"title": r["title"], "url": r["url"], "tag": r["tag"],
                 "source": r.get("source", ""), "timestamp": r.get("timestamp", 0),
                 "summary": ""}
                for r in rows
            ]
        elif self._selected_source:
            self._articles = [a for a in db.get_latest()
                              if a.get("source") == self._selected_source]
        elif self._selected_tag:
            self._articles = db.get_latest(tag=self._selected_tag)
        else:
            self._articles = db.get_latest()

        for a in self._articles:
            title = _strip_markup(a.get("title") or "—")
            if len(title) > 72:
                title = title[:69] + "…"
            t.add_row(
                _fmt_date(a.get("timestamp", 0)),
                (a.get("tag")    or "")[:16],
                (a.get("source") or "")[:14],
                title,
            )

        n = len(self._articles)
        self._set_status(f"{n} article{'s' if n != 1 else ''}")

    # ── events ────────────────────────────────────────────────────────────

    @on(ListView.Selected, "#feed-list")
    def on_feed_select(self, event: ListView.Selected):
        data = getattr(event.item, "data", {})
        kind = data.get("type")
        if kind == "all":
            self._selected_tag    = None
            self._selected_source = None
        elif kind == "cat":
            self._selected_tag    = data["tag"]
            self._selected_source = None
        elif kind == "feed":
            self._selected_source = data["name"]
            self._selected_tag    = None
        self._reload_articles()

    @on(DataTable.RowSelected, "#table")
    def on_row_select(self, event: DataTable.RowSelected):
        idx = event.cursor_row
        if 0 <= idx < len(self._articles):
            self.push_screen(ArticleModal(self._articles[idx]), self._after_article)

    def _after_article(self, result):
        if result == "marked":
            self._reload_articles()
            self.notify("Marked as viewed — won't appear again.")

    @on(Button.Pressed, "#btn-add-feed")
    def _on_btn_add(self): self.action_add_feed()

    @on(Button.Pressed, "#btn-del-feed")
    def _on_btn_del(self): self.action_delete_feed()

    @on(Input.Changed, "#search")
    def on_search_change(self, event: Input.Changed):
        self._reload_articles(search=event.value.strip())

    # ── actions ───────────────────────────────────────────────────────────

    def action_add_feed(self):
        self.push_screen(AddFeedModal(), self._after_add)

    def _after_add(self, result):
        if result:
            db.add_feed(url=result["url"], tag=result["tag"],
                        name=result["name"], feed_type=result["type"])
            self._reload_sidebar()
            self.notify(f"Added: {result['name']}")

    def action_delete_feed(self):
        lv   = self.query_one("#feed-list", ListView)
        item = lv.highlighted_child
        if item is None:
            self.notify("Highlight a feed in the sidebar first.", severity="warning")
            return
        data = getattr(item, "data", {})
        if data.get("type") != "feed":
            self.notify("Select a specific feed, not a category.", severity="warning")
            return
        self.push_screen(
            ConfirmModal(f"Delete '{data['name']}' and all its articles?"),
            lambda ok: self._do_delete(ok, data["url"]),
        )

    def _do_delete(self, confirmed: bool, url: str):
        if confirmed:
            db.remove_feed(url)
            self._selected_source = None
            self._reload_sidebar()
            self._reload_articles()
            self.notify("Feed deleted.", severity="warning")

    def action_fetch(self):
        self._set_status("Fetching…")
        self._fetch_worker()

    @work(thread=True)
    def _fetch_worker(self):
        log = self.app.query_one("#log", RichLog)
        self.call_from_thread(self._show_log_pane)
        log.write("── Curator fetch started ──")
        saved, errors = fetcher.fetch_all()
        log.write(f"Saved {saved} new article(s).")
        for err in errors:
            log.write(f"  ERROR: {err}")
        log.write("── Done ──")
        self.call_from_thread(self._reload_articles)
        self.call_from_thread(self._set_status, f"{saved} new")
        self.call_from_thread(self.notify, f"Fetched {saved} new article(s).")

    def action_toggle_log(self):
        if self._log_visible:
            self._hide_log_pane()
        else:
            self._show_log_pane()

    def _show_log_pane(self):
        self._log_visible = True
        self.query_one("#log",   RichLog).display   = True
        self.query_one("#table", DataTable).display = False
        self.query_one("#pane-label", Label).update("  LOG  ·  press L to return")

    def _hide_log_pane(self):
        self._log_visible = False
        self.query_one("#log",   RichLog).display   = False
        self.query_one("#table", DataTable).display = True
        self.query_one("#pane-label", Label).update("  ARTICLES  ·  L for log")

    def action_open_search(self):
        self.query_one("#search", Input).focus()

    def action_close_search(self):
        inp = self.query_one("#search", Input)
        if inp.value:
            inp.value = ""
            self._reload_articles()
        self.query_one("#table", DataTable).focus()

    def _set_status(self, text: str):
        self.query_one("#status", Label).update(text)