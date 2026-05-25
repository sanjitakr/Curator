#!/usr/bin/env python3
"""
Curator — personal feed reader
CLI entry point.  Also runnable directly: python3 main.py <command>
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import typer
from curator import database as db
from curator import extract


app = typer.Typer(
    name    = "curator",
    help    = "Curator — personal feed reader",
    add_completion = False,
)


@app.command("add-feed")
def add_feed(url:str=typer.Argument(...,help="Feed URL"),
    category: str = typer.Argument(...,help="Category label  e.g. Machine Learning"),
    name:str = typer.Argument("",help="Display name (optional)"),
    feed_type:str=typer.Option(
        "rss", "--type", "-t",
        help="Feed type: rss | youtube | spotify | blog | podcast",
    ),):
    db.add_feed(url=url, tag=category, name=name or url, feed_type=feed_type)
    typer.echo(f"✓  Added: {name or url}  [{category.upper()}]")


@app.command("remove-feed")
def remove_feed(url: str = typer.Argument(..., help="Exact URL of the feed to remove"),):
    """Remove a feed and delete all its articles from the database."""
    db.remove_feed(url)
    typer.echo(f"✓  Removed feed and all its articles: {url}")


@app.command("display-category")
def display_category():
    feeds=db.get_feeds()
    if not feeds:
        typer.echo("No feeds added yet.  Run: curator add-feed <url> <category>")
        raise typer.Exit()
    by_cat:dict[str,list]={}
    for f in feeds:
        by_cat.setdefault(f["tag"], []).append(f)
    for cat, flist in sorted(by_cat.items()):
        typer.echo(f"\n  {cat}")
        typer.echo("  " + "─" * 40)
        for f in flist:
            mark = "✓" if f["enabled"] else "✗"
            typer.echo(f"  {mark}  {f['name']:<28} {f['url']}")


@app.command("list-feeds")
def list_feeds():
    feeds = db.get_feeds()
    if not feeds:
        typer.echo("No feeds added yet.  Run: curator add-feed <url> <category>")
        raise typer.Exit()
    col_name=max(len(f["name"]) for f in feeds)
    col_tag=max(len(f["tag"])  for f in feeds)
    typer.echo(f"  {'NAME':<{col_name}}  {'CATEGORY':<{col_tag}}  {'TYPE':<8}  URL")
    typer.echo("  " + "─" * (col_name + col_tag + 60))
    for f in feeds:
        mark = "✓" if f["enabled"] else "✗"
        typer.echo(
            f"  {mark} {f['name']:<{col_name}}  {f['tag']:<{col_tag}}"
            f"  {f.get('type','rss'):<8}  {f['url']}"
        )



@app.command("latest")
def latest(
    category: str = typer.Option(None, "--category", "-c", help="Filter by category"),
):
    rows = db.get_latest(tag=category)
    if not rows:
        typer.echo("No unread articles.  Try: curator fetch")
        raise typer.Exit()
    for r in rows:
        typer.echo(f"[{r['tag']}]  {r['title']}")
        typer.echo(f"   {r['url']}\n")


@app.command("fetch")
def fetch():
    typer.echo("Fetching feeds…")
    saved, errors = extract.fetch_all()
    typer.echo(f"✓  Saved {saved} new article(s).")
    for err in errors:
        typer.echo(f"   ✗  {err}", err=True)


@app.command("mark-viewed")
def mark_viewed(
    url: str = typer.Argument(..., help="Article URL to dismiss permanently"),):
    """Dismiss an article so it never reappears after future fetches."""
    db.mark_viewed(url)
    typer.echo(f"✓  Dismissed: {url}")


@app.command("search")
def search(
    keyword: str = typer.Argument(..., help="Keyword to search for"),):
    rows = db.search_articles(keyword)
    if not rows:
        typer.echo(f"No results for '{keyword}'.")
        raise typer.Exit()
    for r in rows:
        typer.echo(f"[{r['tag']}]  {r['title']}")
        typer.echo(f"   {r['url']}\n")

@app.command("ui")
def ui():
    from curator.tui import CuratorApp
    CuratorApp().run()


if __name__ == "__main__":
    app()