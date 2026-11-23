#!/usr/bin/env python3
"""Generate the profile hero from public GitHub profile and repository data."""

from collections import Counter
from datetime import datetime, timezone
from html import escape
import json
import os
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


API = "https://api.github.com"
OUTPUT = Path(__file__).resolve().parents[1] / "assets" / "hero.svg"
COLORS = ["#f5c16c", "#f28a62", "#de6680", "#aa78b7", "#7d91ca"]


def get_json(url):
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "profile-hero-generator",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = Request(url, headers=headers)
    try:
        with urlopen(request, timeout=30) as response:
            return json.load(response)
    except HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"GitHub API request failed ({error.code}): {detail}") from error


def fetch_profile(login):
    profile = get_json(f"{API}/users/{login}")
    repos = []
    page = 1
    while True:
        query = urlencode({"type": "owner", "per_page": 100, "page": page, "sort": "updated"})
        batch = get_json(f"{API}/users/{login}/repos?{query}")
        repos.extend(repo for repo in batch if not repo.get("private", False))
        if len(batch) < 100:
            break
        page += 1
    return profile, repos


def xml(value):
    return escape(str(value), quote=True)


def make_scene():
    columns, rows = 36, 13
    center_x, center_y = 17.5, 5.2
    radius_x, radius_y = 10.5, 4.8
    slats = {6, 8, 10}
    palette = ["#ffe0a0", "#ffc06e", "#f59660", "#e57470", "#c86c91"]
    art = []
    for row in range(rows):
        cells = []
        for column in range(columns):
            dx = (column - center_x) / radius_x
            dy = (row - center_y) / radius_y
            inside = dx * dx + dy * dy <= 1
            if inside and row not in slats:
                depth = max(0, min(len(palette) - 1, int((row / rows) * len(palette))))
                character = "@%#*+="[min(5, int((abs(dx) + abs(dy)) * 3))]
                color = palette[depth]
            elif row >= 10 and (column + row * 2) % max(3, row - 7) == 0:
                character, color = ("/" if column < center_x else "\\"), "#a66f9a"
            elif row < 5 and (row * 29 + column * 13) % 61 == 0:
                character, color = ".", "#888da7"
            else:
                character, color = " ", "#777"
            cells.append((character, color))
        art.append(cells)
    return art


def scene_svg():
    output = []
    x0, y0, cell_width, line_height = 42, 133, 9, 17
    for row_index, row in enumerate(make_scene()):
        column = 0
        while column < len(row):
            character, color = row[column]
            if character == " ":
                column += 1
                continue
            start = column
            text = []
            while column < len(row) and row[column][1] == color:
                text.append(row[column][0])
                column += 1
            output.append(
                f'<text x="{x0 + start * cell_width}" y="{y0 + row_index * line_height}" '
                f'fill="{color}" font-family="monospace" font-size="15" xml:space="preserve">'
                f'{xml("".join(text))}</text>'
            )
    return "\n".join(output)


def member_duration(created_at, today):
    created = datetime.fromisoformat(created_at.replace("Z", "+00:00")).date()
    years = today.year - created.year - ((today.month, today.day) < (created.month, created.day))
    return f"{years} year{'s' if years != 1 else ''}" if years else "under 1 year"


def render(profile, repos, today=None):
    today = today or datetime.now(timezone.utc).date()
    login = profile["login"]
    name = profile.get("name") or login
    stars = sum(int(repo.get("stargazers_count") or 0) for repo in repos)
    languages = Counter(repo["language"] for repo in repos if repo.get("language"))
    top_languages = languages.most_common(5)
    max_count = max((count for _, count in top_languages), default=1)

    stats = [
        ("PUBLIC REPOS", profile.get("public_repos", len(repos))),
        ("STARS", stars),
        ("FOLLOWERS", profile.get("followers", 0)),
        ("ON GITHUB", member_duration(profile["created_at"], today)),
    ]
    stat_svg = []
    for index, (label, value) in enumerate(stats):
        x = 432 + (index % 2) * 274
        y = 128 + (index // 2) * 63
        stat_svg.append(
            f'<text x="{x}" y="{y}" class="label">{xml(label)}</text>'
            f'<text x="{x}" y="{y + 27}" class="value">{xml(value)}</text>'
        )

    language_svg = []
    for index, (language, count) in enumerate(top_languages):
        y = 282 + index * 17
        width = 145 * count / max_count
        language_svg.append(
            f'<text x="432" y="{y}" class="small">{xml(language[:18])}</text>'
            f'<rect x="565" y="{y - 10}" width="145" height="7" rx="3.5" fill="#343442"/>'
            f'<rect x="565" y="{y - 10}" width="{width:.1f}" height="7" rx="3.5" fill="{COLORS[index]}"/>'
            f'<text x="721" y="{y}" class="small">{count}</text>'
        )
    if not top_languages:
        language_svg.append('<text x="432" y="282" class="small">No public language data</text>')

    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="960" height="390" viewBox="0 0 960 390" role="img" aria-labelledby="title description">
  <title id="title">{xml(name)} — live GitHub profile</title>
  <desc id="description">A terminal-style profile card with GitHub repository, star, follower, tenure, and primary-language statistics.</desc>
  <defs>
    <linearGradient id="background" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="#151923"/>
      <stop offset="1" stop-color="#242230"/>
    </linearGradient>
    <style>
      .label {{ fill: #9798a7; font: 11px ui-monospace, SFMono-Regular, Consolas, monospace; letter-spacing: 1.2px; }}
      .value {{ fill: #f5eee5; font: 22px ui-monospace, SFMono-Regular, Consolas, monospace; }}
      .small {{ fill: #b6b5c0; font: 11px ui-monospace, SFMono-Regular, Consolas, monospace; }}
    </style>
  </defs>
  <rect width="960" height="390" rx="20" fill="url(#background)"/>
  <rect x="1" y="1" width="958" height="388" rx="19" fill="none" stroke="#42404c"/>
  <circle cx="27" cy="27" r="5" fill="#ef8065"/><circle cx="46" cy="27" r="5" fill="#f2bc74"/><circle cx="65" cy="27" r="5" fill="#8da58b"/>
  <text x="86" y="31" fill="#aaa9b4" font-family="monospace" font-size="12">{xml(login)}@github:~ $ profile --refresh</text>
  <path d="M24 50h912" stroke="#393744"/>
  <text x="42" y="83" fill="#f1bc75" font-family="monospace" font-size="12" letter-spacing="1.5">LIVE PROFILE / PUBLIC GITHUB DATA</text>
  {scene_svg()}
  <text x="42" y="363" fill="#9996a4" font-family="monospace" font-size="11">repo language mix · refreshed {today.isoformat()}</text>
  <path d="M407 72v282" stroke="#44414e"/>
  <text x="432" y="88" fill="#f7f1e9" font-family="system-ui, sans-serif" font-size="27" font-weight="700">{xml(name[:32])}</text>
  <text x="432" y="108" fill="#d58c71" font-family="monospace" font-size="12">@{xml(login)}</text>
  {''.join(stat_svg)}
  <path d="M432 257h482" stroke="#44414e"/>
  <text x="432" y="274" class="label">PRIMARY LANGUAGES · REPOSITORY COUNT</text>
  {''.join(language_svg)}
</svg>
'''


def main():
    login = os.environ.get("GH_USER", "maxzhang666")
    profile, repos = fetch_profile(login)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(render(profile, repos), encoding="utf-8")
    print(f"Generated {OUTPUT} from {profile['login']}'s public GitHub data.")


if __name__ == "__main__":
    main()
