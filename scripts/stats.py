#!/usr/bin/env python3
"""Generate terminal-style GitHub stats cards (SVG) for a profile README.

Runs in GitHub Actions with the built-in GITHUB_TOKEN. Uses only the
standard library and the GitHub REST API.

Usage: python scripts/stats.py <username> <output_dir>
"""
import json
import os
import sys
import urllib.request
from html import escape

API = "https://api.github.com"
BG, GREEN, TEXT, DIM = "#0A0F0A", "#33FF66", "#A8FFB8", "#1C3A22"
FONT = "'VT323','IBM Plex Mono','SFMono-Regular',Consolas,'Liberation Mono',monospace"
# green ramp for the language bar, brightest first
SHADES = ["#33FF66", "#22C55E", "#86EFAC", "#15803D", "#BBF7D0", "#166534"]


def get(path):
    req = urllib.request.Request(API + path, headers={
        "Accept": "application/vnd.github+json",
        "User-Agent": "profile-stats",
        **({"Authorization": f"Bearer {os.environ['GITHUB_TOKEN']}"}
           if os.environ.get("GITHUB_TOKEN") else {}),
    })
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def count(query):
    try:
        return get(f"/search/issues?q={query}&per_page=1")["total_count"]
    except Exception:
        return None


def collect(user):
    repos, page = [], 1
    while True:
        batch = get(f"/users/{user}/repos?per_page=100&page={page}&type=owner")
        repos += batch
        if len(batch) < 100:
            break
        page += 1
    own = [r for r in repos if not r["fork"]]
    langs = {}
    for r in own:
        for lang, n in get(f"/repos/{user}/{r['name']}/languages").items():
            langs[lang] = langs.get(lang, 0) + n
    try:
        commits = get(f"/search/commits?q=author:{user}&per_page=1")["total_count"]
    except Exception:
        commits = None
    return {
        "commits": commits,
        "prs": count(f"author:{user}+type:pr"),
        "merged": count(f"author:{user}+type:pr+is:merged"),
        "issues": count(f"author:{user}+type:issue"),
        "stars": sum(r["stargazers_count"] for r in own),
        "repos": len(own),
        "langs": langs,
    }


def frame(w, h, title, body):
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" role="img" aria-label="{escape(title)}">
<title>{escape(title)}</title>
<style>text{{font-family:{FONT};}}</style>
<rect width="{w}" height="{h}" rx="6" fill="{BG}"/>
<rect x="0.5" y="0.5" width="{w-1}" height="{h-1}" rx="6" fill="none" stroke="{DIM}"/>
<circle cx="18" cy="16" r="4" fill="{DIM}"/><circle cx="32" cy="16" r="4" fill="{DIM}"/><circle cx="46" cy="16" r="4" fill="{DIM}"/>
{body}
</svg>
"""


def fmt(v):
    return "—" if v is None else f"{v:,}"


def stats_svg(user, s):
    rows = [("commits", s["commits"]), ("pull_requests", s["prs"]),
            ("merged_prs", s["merged"]), ("issues", s["issues"]),
            ("stars_earned", s["stars"]), ("public_repos", s["repos"])]
    body = [f'<text x="20" y="48" fill="{GREEN}" font-size="17">&gt; git stats --user {escape(user)}</text>']
    for i, (k, v) in enumerate(rows):
        y = 76 + i * 20
        dots = "." * (16 - len(k))
        body.append(f'<text x="20" y="{y}" font-size="15" xml:space="preserve">'
                    f'<tspan fill="{GREEN}">+ </tspan><tspan fill="{TEXT}">{k} </tspan>'
                    f'<tspan fill="{DIM}">{dots}</tspan>'
                    f'<tspan fill="{GREEN}" font-weight="bold"> {fmt(v)}</tspan></text>')
    return frame(400, 200, f"GitHub stats for {user}", "\n".join(body))


def langs_svg(user, langs, top=6):
    total = sum(langs.values()) or 1
    items = sorted(langs.items(), key=lambda x: -x[1])[:top]
    body = [f'<text x="20" y="48" fill="{GREEN}" font-size="17">&gt; cat top_languages.log</text>']
    x, bar_w = 20, 360
    for i, (lang, n) in enumerate(items):
        w = bar_w * n / total
        body.append(f'<rect x="{x:.1f}" y="62" width="{max(w, 1.5):.1f}" height="8" fill="{SHADES[i % len(SHADES)]}"/>')
        x += w
    for i, (lang, n) in enumerate(items):
        col, row = i % 2, i // 2
        cx, cy = 20 + col * 185, 98 + row * 24
        body.append(f'<rect x="{cx}" y="{cy-9}" width="9" height="9" fill="{SHADES[i % len(SHADES)]}"/>'
                    f'<text x="{cx+16}" y="{cy}" font-size="15" fill="{TEXT}">{escape(lang)} '
                    f'<tspan fill="{GREEN}">{100*n/total:.1f}%</tspan></text>')
    return frame(400, 200, f"Top languages for {user}", "\n".join(body))


def main():
    user = sys.argv[1]
    out = sys.argv[2] if len(sys.argv) > 2 else "assets"
    os.makedirs(out, exist_ok=True)
    s = collect(user)
    with open(os.path.join(out, "stats.svg"), "w") as f:
        f.write(stats_svg(user, s))
    with open(os.path.join(out, "top-langs.svg"), "w") as f:
        f.write(langs_svg(user, s["langs"]))
    print(json.dumps({k: v for k, v in s.items() if k != "langs"}))


if __name__ == "__main__":
    main()
