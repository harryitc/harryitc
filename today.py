#!/usr/bin/env python3
"""Render the neofetch-style profile SVGs from live GitHub data.

    python today.py              # needs ACCESS_TOKEN, hits the API
    python today.py --offline    # placeholder numbers, for checking the layout

Writes dark_mode.svg and light_mode.svg next to this file. If the API call
fails the script exits non-zero without touching the SVGs, so a broken run
leaves yesterday's profile in place rather than blanking it.
"""

import argparse
import datetime
import json
import os
import sys
from pathlib import Path
from xml.sax.saxutils import escape

import requests

import profile_config as cfg

ROOT = Path(__file__).parent
CACHE_FILE = ROOT / "cache" / "loc.json"
API_URL = "https://api.github.com/graphql"

# Every info row is padded out to this many characters so the dot leaders in
# each section line up with each other.
COLUMNS = 64

FONT_SIZE = 13
# Slightly wider than the 0.6em most monospace faces use, so a font with roomy
# advance widths still leaves a margin instead of running into the border.
CHAR_WIDTH = FONT_SIZE * 0.63
ART_LINE_HEIGHT = 15
INFO_LINE_HEIGHT = 19
PADDING = 24
GUTTER = 32


class GitHubError(RuntimeError):
    pass


# --------------------------------------------------------------------------
# GitHub API
# --------------------------------------------------------------------------

def query(session, document, variables):
    response = session.post(
        API_URL, json={"query": document, "variables": variables}, timeout=30
    )
    if response.status_code != 200:
        raise GitHubError(f"HTTP {response.status_code} from GitHub: {response.text[:300]}")
    payload = response.json()
    if "errors" in payload:
        raise GitHubError(f"GraphQL errors: {json.dumps(payload['errors'])[:300]}")
    return payload["data"]


USER_QUERY = """
query ($login: String!) {
  user(login: $login) {
    id
    createdAt
    followers { totalCount }
    repositoriesContributedTo(
      contributionTypes: [COMMIT, ISSUE, PULL_REQUEST, REPOSITORY]
    ) { totalCount }
  }
}
"""

REPOS_QUERY = """
query ($login: String!, $cursor: String) {
  user(login: $login) {
    repositories(first: 100, after: $cursor, ownerAffiliations: OWNER) {
      totalCount
      pageInfo { hasNextPage endCursor }
      nodes {
        nameWithOwner
        stargazerCount
        defaultBranchRef { name }
      }
    }
  }
}
"""

COMMITS_QUERY = """
query ($login: String!, $from: DateTime!, $to: DateTime!) {
  user(login: $login) {
    contributionsCollection(from: $from, to: $to) {
      totalCommitContributions
      restrictedContributionsCount
    }
  }
}
"""

HISTORY_QUERY = """
query ($owner: String!, $name: String!, $author: ID!, $cursor: String) {
  repository(owner: $owner, name: $name) {
    defaultBranchRef {
      target {
        ... on Commit {
          history(first: 100, after: $cursor, author: {id: $author}) {
            totalCount
            pageInfo { hasNextPage endCursor }
            nodes { additions deletions }
          }
        }
      }
    }
  }
}
"""


def fetch_user(session, login):
    data = query(session, USER_QUERY, {"login": login})["user"]
    if data is None:
        raise GitHubError(f"no such GitHub user: {login}")
    return data


def fetch_repos(session, login):
    repos, cursor = [], None
    while True:
        page = query(session, REPOS_QUERY, {"login": login, "cursor": cursor})
        block = page["user"]["repositories"]
        repos.extend(block["nodes"])
        if not block["pageInfo"]["hasNextPage"]:
            return repos, block["totalCount"]
        cursor = block["pageInfo"]["endCursor"]


def fetch_commit_total(session, login, created_at):
    """Commit contributions, summed year by year.

    contributionsCollection only covers a one-year window, so all-time totals
    mean one call per year since the account was created.
    """
    start = datetime.datetime.fromisoformat(created_at.replace("Z", "+00:00"))
    now = datetime.datetime.now(datetime.timezone.utc)
    total = 0
    while start < now:
        end = min(start + datetime.timedelta(days=365), now)
        block = query(session, COMMITS_QUERY, {
            "login": login,
            "from": start.isoformat().replace("+00:00", "Z"),
            "to": end.isoformat().replace("+00:00", "Z"),
        })["user"]["contributionsCollection"]
        total += block["totalCommitContributions"] + block["restrictedContributionsCount"]
        start = end
    return total


def load_cache():
    if CACHE_FILE.exists():
        try:
            return json.loads(CACHE_FILE.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass  # a corrupt cache is not worth failing the run over
    return {}


def save_cache(cache):
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    CACHE_FILE.write_text(json.dumps(cache, indent=1, sort_keys=True), encoding="utf-8")


def fetch_lines_of_code(session, login, author_id, repos):
    """Sum additions and deletions across every repo you own.

    Walking full commit history is the expensive part of this script, so each
    repo's result is cached against its commit count. A repo nobody has pushed
    to since the last run costs one request instead of one per hundred commits.
    """
    cache = load_cache()
    additions = deletions = 0

    for repo in repos:
        name_with_owner = repo["nameWithOwner"]
        if name_with_owner in cfg.EXCLUDED_REPOS or repo["defaultBranchRef"] is None:
            continue

        owner, name = name_with_owner.split("/", 1)
        cursor, repo_add, repo_del, total_commits = None, 0, 0, None

        while True:
            target = query(session, HISTORY_QUERY, {
                "owner": owner, "name": name, "author": author_id, "cursor": cursor,
            })["repository"]["defaultBranchRef"]["target"]
            history = target["history"]

            if total_commits is None:
                total_commits = history["totalCount"]
                cached = cache.get(name_with_owner)
                if cached and cached["commits"] == total_commits:
                    repo_add, repo_del = cached["additions"], cached["deletions"]
                    break

            for node in history["nodes"]:
                repo_add += node["additions"]
                repo_del += node["deletions"]
            if not history["pageInfo"]["hasNextPage"]:
                cache[name_with_owner] = {
                    "commits": total_commits,
                    "additions": repo_add,
                    "deletions": repo_del,
                }
                break
            cursor = history["pageInfo"]["endCursor"]

        additions += repo_add
        deletions += repo_del

    save_cache(cache)
    return additions, deletions


# --------------------------------------------------------------------------
# Formatting
# --------------------------------------------------------------------------

def format_uptime(since):
    """Whole years, months and days between `since` and today."""
    today = datetime.date.today()
    years = today.year - since.year
    months = today.month - since.month
    days = today.day - since.day
    if days < 0:
        months -= 1
        previous_month = today.replace(day=1) - datetime.timedelta(days=1)
        days += previous_month.day
    if months < 0:
        years -= 1
        months += 12

    parts = []
    for value, unit in ((years, "year"), (months, "month"), (days, "day")):
        if value or unit == "day":
            parts.append(f"{value} {unit}{'' if value == 1 else 's'}")
    return ", ".join(parts)


def leader(label, value):
    """`label: ...... value`, padded so every row ends at the same column."""
    prefix = f"{label}:"
    fill = COLUMNS - len(prefix) - len(value) - 2
    return f"{prefix} {'.' * max(fill, 1)} {value}"


def rule(title):
    body = f"─ {title} " if title else ""
    return body + "─" * max(COLUMNS - len(body), 1)


def build_rows(stats):
    """Every info row, as a list of (text, css-class) segments."""
    rows = []

    def row(label, value, value_class="val"):
        if value is None:
            return
        text = leader(label, value)
        split = len(label) + 1
        dots_end = len(text) - len(value)
        rows.append([
            (text[:split - 1], "key"),
            (text[split - 1:dots_end], "dot"),
            (value, value_class),
        ])

    rows.append([(rule(f"{cfg.USER_NAME}@github"), "hdr")])
    for label, value in cfg.SYSTEM:
        row(label, stats["uptime"] if label == "Uptime" else value)

    rows.append([])
    for label, value in cfg.LANGUAGES + cfg.HOBBIES:
        row(label, value)

    rows.append([])
    rows.append([(rule("Contact"), "hdr")])
    for label, value in cfg.CONTACT:
        row(label, value)

    rows.append([])
    rows.append([(rule("GitHub Stats"), "hdr")])
    row("Repos", f"{stats['repos']:,}")
    row("Contributed", f"{stats['contributed']:,}")
    row("Stars", f"{stats['stars']:,}")
    row("Commits", f"{stats['commits']:,}")
    row("Followers", f"{stats['followers']:,}")

    # The lines-of-code row needs three colours, so it is assembled by hand.
    total = stats["additions"] + stats["deletions"]
    tail = f"{total:,} ({stats['additions']:,}++, {stats['deletions']:,}--)"
    text = leader("Lines of Code", tail)
    dots_end = len(text) - len(tail)
    rows.append([
        ("Lines of Code", "key"),
        (text[len("Lines of Code"):dots_end], "dot"),
        (f"{total:,} (", "val"),
        (f"{stats['additions']:,}++", "add"),
        (", ", "val"),
        (f"{stats['deletions']:,}--", "del"),
        (")", "val"),
    ])
    return rows


def render(template, art_lines, rows):
    art_width = max((len(line) for line in art_lines), default=0)
    info_x = PADDING + art_width * CHAR_WIDTH + GUTTER
    width = round(info_x + COLUMNS * CHAR_WIDTH + PADDING)
    height = round(max(
        len(art_lines) * ART_LINE_HEIGHT,
        len(rows) * INFO_LINE_HEIGHT,
    ) + PADDING * 2)

    art_svg = []
    for index, line in enumerate(art_lines):
        y = PADDING + (index + 1) * ART_LINE_HEIGHT
        art_svg.append(
            f'<text class="art" x="{PADDING}" y="{y}" xml:space="preserve">'
            f"{escape(line)}</text>"
        )

    info_svg = []
    for index, segments in enumerate(rows):
        if not segments:
            continue
        y = PADDING + (index + 1) * INFO_LINE_HEIGHT
        spans = "".join(
            f'<tspan class="{css}">{escape(text)}</tspan>' for text, css in segments
        )
        info_svg.append(
            f'<text x="{round(info_x)}" y="{y}" xml:space="preserve">{spans}</text>'
        )

    return (template
            .replace("{{WIDTH1}}", str(width - 1))
            .replace("{{HEIGHT1}}", str(height - 1))
            .replace("{{WIDTH}}", str(width))
            .replace("{{HEIGHT}}", str(height))
            .replace("{{FONT_SIZE}}", str(FONT_SIZE))
            .replace("{{ART}}", "\n".join(art_svg))
            .replace("{{INFO}}", "\n".join(info_svg)))


# --------------------------------------------------------------------------

PLACEHOLDER_STATS = {
    "repos": 0, "contributed": 0, "stars": 0, "commits": 0,
    "followers": 0, "additions": 0, "deletions": 0,
}


def gather_stats(token, login):
    session = requests.Session()
    session.headers.update({"Authorization": f"bearer {token}"})

    user = fetch_user(session, login)
    repos, repo_count = fetch_repos(session, login)
    additions, deletions = fetch_lines_of_code(session, login, user["id"], repos)

    return {
        "repos": repo_count,
        "contributed": user["repositoriesContributedTo"]["totalCount"],
        "stars": sum(repo["stargazerCount"] for repo in repos),
        "followers": user["followers"]["totalCount"],
        "commits": fetch_commit_total(session, login, user["createdAt"]),
        "additions": additions,
        "deletions": deletions,
        "created_at": user["createdAt"],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--offline", action="store_true",
                        help="skip the API and render with zeroed stats")
    args = parser.parse_args()

    if args.offline:
        stats = dict(PLACEHOLDER_STATS, created_at="2020-01-01T00:00:00Z")
    else:
        token = os.environ.get("ACCESS_TOKEN")
        if not token:
            print("ACCESS_TOKEN is not set. Use --offline to preview the layout.",
                  file=sys.stderr)
            return 1
        try:
            stats = gather_stats(token, cfg.USER_NAME)
        except (GitHubError, requests.RequestException) as error:
            print(f"leaving the existing SVGs alone: {error}", file=sys.stderr)
            return 1

    if cfg.BIRTHDAY:
        since = datetime.date.fromisoformat(cfg.BIRTHDAY)
    else:
        since = datetime.datetime.fromisoformat(
            stats["created_at"].replace("Z", "+00:00")).date()
    stats["uptime"] = format_uptime(since)

    art_lines = (ROOT / "ascii_art.txt").read_text(encoding="utf-8").split("\n")
    while art_lines and not art_lines[-1].strip():
        art_lines.pop()
    rows = build_rows(stats)

    for mode in ("dark", "light"):
        template = (ROOT / "templates" / f"{mode}_mode.svg").read_text(encoding="utf-8")
        (ROOT / f"{mode}_mode.svg").write_text(render(template, art_lines, rows),
                                               encoding="utf-8")
        print(f"wrote {mode}_mode.svg")
    return 0


if __name__ == "__main__":
    sys.exit(main())
