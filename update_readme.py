#!/usr/bin/env python3
"""
Updates README.md with:
  - ASCII art from ascii_art.txt (you maintain this file)
  - Live GitHub stats via API
  - Calculated age (uptime) from birthday

Runs via GitHub Actions on every push + daily cron.

HOW TO UPDATE:
  1. Edit ascii_art.txt with any ASCII art you want
  2. Push to GitHub — the workflow auto-updates the README
  3. To change personal info, edit the INFO section below
"""

from __future__ import annotations

import os
import re
import json
import calendar
import urllib.request
import urllib.error
from datetime import date


# ══════════════════════════════════════════════════════════════════════════
# CONFIGURATION — Edit these to customize your profile
# ══════════════════════════════════════════════════════════════════════════

GITHUB_USERNAME = "Faysal1000"
BIRTHDAY = date(2001, 4, 25)
README_PATH = "README.md"
ASCII_ART_PATH = "ascii_art.txt"


def read_ascii_art() -> list[str]:
    """Read ASCII art from the text file."""
    if not os.path.exists(ASCII_ART_PATH):
        print(f"⚠️  {ASCII_ART_PATH} not found!")
        return ["  (no ascii art found)"]

    with open(ASCII_ART_PATH, "r", encoding="utf-8") as f:
        lines = f.readlines()

    # Strip all trailing whitespace (spaces + newlines) to get true widths
    lines = [line.rstrip() for line in lines]
    while lines and not lines[-1].strip():
        lines.pop()

    return lines


def calculate_uptime(birthday: date) -> str:
    """Calculate age as 'X years, Y months, Z days'."""
    today = date.today()
    years = today.year - birthday.year
    months = today.month - birthday.month
    days = today.day - birthday.day

    if days < 0:
        months -= 1
        prev_month = today.month - 1 if today.month > 1 else 12
        prev_year = today.year if today.month > 1 else today.year - 1
        days += calendar.monthrange(prev_year, prev_month)[1]

    if months < 0:
        years -= 1
        months += 12

    return f"{years} years, {months} months, {days} days"


def load_env():
    """Load environment variables from .env if present."""
    env_file = os.path.join(os.path.dirname(__file__), ".env")
    if os.path.exists(env_file):
        with open(env_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def github_api(endpoint: str) -> dict | list:
    """Make a GitHub API request."""
    load_env()
    url = f"https://api.github.com{endpoint}"
    headers = {
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": GITHUB_USERNAME,
    }
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"token {token}"

    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        reset_time = e.headers.get("X-RateLimit-Reset")
        if e.code == 403 and reset_time:
            from datetime import datetime
            reset_dt = datetime.fromtimestamp(int(reset_time))
            print(f"⚠️  GitHub API Rate Limit reached! Limit resets at {reset_dt.strftime('%H:%M:%S')}.")
            print("   Tip: Add GH_TOKEN=your_token in .env for 5,000 requests/hr.")
        else:
            print(f"GitHub API error: {e.code} for {url}")
        return {}


def get_github_stats() -> dict:
    """Fetch GitHub profile stats including LOC."""
    user = github_api(f"/users/{GITHUB_USERNAME}")

    repos = []
    page = 1
    while True:
        batch = github_api(f"/users/{GITHUB_USERNAME}/repos?per_page=100&page={page}")
        if not batch or not isinstance(batch, list):
            break
        repos.extend(batch)
        if len(batch) < 100:
            break
        page += 1

    total_stars = sum(r.get("stargazers_count", 0) for r in repos)
    public_repos = user.get("public_repos", len(repos)) if isinstance(user, dict) else len(repos)
    followers = user.get("followers", 0) if isinstance(user, dict) else 0
    following = user.get("following", 0) if isinstance(user, dict) else 0

    # Fetch commits count and LOC (lines added/deleted)
    total_commits = 0
    total_additions = 0
    total_deletions = 0

    for repo in repos:
        if repo.get("fork"):
            continue  # Skip forks
        repo_name = repo.get("full_name", "")
        if not repo_name:
            continue

        # Get contributor stats (includes additions/deletions)
        contributors = github_api(f"/repos/{repo_name}/stats/contributors")
        if isinstance(contributors, list):
            for contributor in contributors:
                author = contributor.get("author", {})
                if isinstance(author, dict) and author.get("login", "").lower() == GITHUB_USERNAME.lower():
                    total_commits += contributor.get("total", 0)
                    for week in contributor.get("weeks", []):
                        total_additions += week.get("a", 0)
                        total_deletions += week.get("d", 0)

    stats = {
        "repos": public_repos,
        "stars": total_stars,
        "followers": followers,
        "following": following,
        "commits": total_commits,
        "additions": total_additions,
        "deletions": total_deletions,
    }

    # If rate limited (e.g. public_repos == 0 and commits == 0), try to keep old values from README.md
    if public_repos == 0 and total_commits == 0 and os.path.exists(README_PATH):
        with open(README_PATH, "r", encoding="utf-8") as f:
            old_text = f.read()
        repos_m = re.search(r"Repos:\s*([\d,]+)", old_text)
        commits_m = re.search(r"Commits:\s*([\d,]+)", old_text)
        loc_m = re.search(r"GitHub LOC:\s*[\d,]+\s*\(\s*\+([\d,]+),\s*\-([\d,]+)\s*\)", old_text)
        if repos_m and int(repos_m.group(1).replace(",", "")) > 0:
            stats["repos"] = int(repos_m.group(1).replace(",", ""))
        if commits_m and int(commits_m.group(1).replace(",", "")) > 0:
            stats["commits"] = int(commits_m.group(1).replace(",", ""))
        if loc_m:
            stats["additions"] = int(loc_m.group(1).replace(",", ""))
            stats["deletions"] = int(loc_m.group(2).replace(",", ""))

    return stats


# ══════════════════════════════════════════════════════════════════════════
# INFO — Edit these lines to change what shows in your neofetch
# ══════════════════════════════════════════════════════════════════════════

MAX_WIDTH = 80  # GitHub code block safe width


def build_info_lines(stats: dict, uptime: str) -> list[str]:
    """Build the right-side info panel. Auto-sizes separators."""
    # Format LOC compactly for large numbers
    loc_total = stats['additions'] + stats['deletions']
    if loc_total >= 1_000_000:
        loc_str = (f"{loc_total / 1e6:.1f}M "
                   f"(+{stats['additions'] / 1e6:.1f}M, "
                   f"-{stats['deletions'] / 1e6:.1f}M)")
    elif loc_total >= 1_000:
        loc_str = (f"{loc_total / 1e3:.0f}K "
                   f"(+{stats['additions'] / 1e3:.0f}K, "
                   f"-{stats['deletions'] / 1e3:.0f}K)")
    elif loc_total > 0:
        loc_str = f"{loc_total:,} (+{stats['additions']:,}, -{stats['deletions']:,})"
    else:
        loc_str = "0 (+0, -0)"

    # Key width: 23 chars for full dot-notation keys
    K = 23

    lines = [
        "faysalahmmed",
        "",  # separator placeholder (index 1)
        f"{'OS:':<{K}}Human",
        f"{'Uptime:':<{K}}{uptime}",
        f"{'Host:':<{K}}Dhaka, Bangladesh",
        f"{'Kernel:':<{K}}Computer Scientist",
        f"{'':<{K}}(AI • Robotics • ML)",
        "",
        f"{'Languages.Programming:':<{K}}Python, C++, TypeScript,",
        f"{'':<{K}}C#, MATLAB",
        f"{'Languages.Real:':<{K}}English, Bengali",
        "",
        f"{'Frameworks.ML:':<{K}}PyTorch, TensorFlow,",
        f"{'':<{K}}OpenCV, Scikit-Learn",
        f"{'Frameworks.Backend:':<{K}}Node.js, NestJS, Docker",
        f"{'Frameworks.Frontend:':<{K}}React.js, Tailwind CSS",
        f"{'Database:':<{K}}PostgreSQL, MySQL, Redis",
        "",
        f"{'Research.AI:':<{K}}Multimodal AI, Medical AI,",
        f"{'':<{K}}Computer Vision, Misinfo",
        f"{'Research.Robotics:':<{K}}Humanoid, RL, Medical",
        f"{'':<{K}}Robotics, Motion RT",
        "",
        f"{'Education:':<{K}}BSc CSE (2026), AIUB",
        "",
        "",  # contact separator placeholder (index 25)
        f"{'Portfolio:':<{K}}faysalahmmed.vercel.app",
        f"{'Email:':<{K}}faysalahmmed4200@gmail.com",
        f"{'ORCID:':<{K}}0009-0002-2981-1600",
        f"{'Facebook:':<{K}}faysal.ahmmed.2001",
        "",
        "",  # stats separator placeholder (index 31)
        f"{'Repos:':<{K}}{stats['repos']}",
        f"{'Commits:':<{K}}{stats['commits']:,}",
        f"{'LOC:':<{K}}{loc_str}",
        f"{'Research Years:':<{K}}2+",
        f"{'Publications:':<{K}}9 (Q1/Q2: 5, 1st: 5)",
        f"{'Research Areas:':<{K}}AI • Robotics • Vision",
        "",
        "",  # bottom separator placeholder (index 39)
        f"{'Status:':<{K}}Applying for MS/PhD",
        f"{'':<{K}}in Robotics 🤖",
    ]

    # Auto-size separator lines to match widest content line
    max_info = max(len(line) for line in lines)
    sep = "─" * max_info
    lines[1] = sep
    lines[25] = f"Contact {'─' * (max_info - 8)}"
    lines[31] = f"Stats {'─' * (max_info - 6)}"
    lines[39] = sep



    return lines


def build_neofetch(ascii_lines: list[str], info_lines: list[str]) -> str:
    """Combine ASCII art (left) + info (right) side by side."""

    # Use actual content width (no trailing spaces)
    art_width = max((len(line) for line in ascii_lines), default=0)
    info_width = max((len(line) for line in info_lines), default=0)
    total_width = art_width + 2 + info_width

    if total_width > MAX_WIDTH:
        print(f"⚠️  Total width is {total_width} chars (max {MAX_WIDTH}).")
        print(f"   Art: {art_width}, Info: {info_width}, Gap: 2")
        print(f"   Tip: Shrink your ASCII art to ≤{MAX_WIDTH - 2 - info_width} chars wide.")

    combined = []
    max_lines = max(len(ascii_lines), len(info_lines))

    for i in range(max_lines):
        left = ascii_lines[i] if i < len(ascii_lines) else ""
        right = info_lines[i] if i < len(info_lines) else ""
        combined.append(f"{left:<{art_width}}  {right}")

    return "\n".join(combined)


def update_readme(neofetch_block: str):
    """Replace content between markers in README.md."""
    with open(README_PATH, "r", encoding="utf-8") as f:
        content = f.read()

    start_marker = "<!-- NEOFETCH:START -->"
    end_marker = "<!-- NEOFETCH:END -->"

    pattern = re.compile(
        re.escape(start_marker) + r".*?" + re.escape(end_marker),
        re.DOTALL,
    )

    replacement = f"""{start_marker}
```
{neofetch_block}
```
{end_marker}"""

    if start_marker in content:
        new_content = pattern.sub(replacement, content)
    else:
        new_content = replacement + "\n\n" + content

    with open(README_PATH, "w", encoding="utf-8") as f:
        f.write(new_content)

    print("✅ README.md updated successfully!")


def main():
    # 1. Read ASCII art from file
    print(f"🔄 Reading ASCII art from {ASCII_ART_PATH}...")
    ascii_lines = read_ascii_art()
    print(f"   Loaded {len(ascii_lines)} lines")

    # 2. Fetch GitHub stats
    print("🔄 Fetching GitHub stats...")
    stats = get_github_stats()
    print(f"   Repos: {stats['repos']}, Stars: {stats['stars']}, "
          f"Followers: {stats['followers']}, Following: {stats['following']}")

    # 3. Calculate uptime (age)
    print("🔄 Calculating uptime...")
    uptime = calculate_uptime(BIRTHDAY)
    print(f"   Uptime: {uptime}")

    # 4. Build info lines
    info_lines = build_info_lines(stats, uptime)

    # 5. Build neofetch and update README
    print("🔄 Building neofetch block...")
    block = build_neofetch(ascii_lines, info_lines)

    print("🔄 Updating README.md...")
    update_readme(block)


if __name__ == "__main__":
    main()
