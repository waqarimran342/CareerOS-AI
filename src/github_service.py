"""
GitHub service for CareerOS AI.

Fetches real evidence about a developer from the public GitHub REST API:
profile stats, repositories, languages, stars and activity. This is what
lets CareerOS verify skills instead of trusting the resume alone.

A personal access token is OPTIONAL (60 requests/hour without one,
5000/hour with one). See GITHUB_TOKEN in .env.example.
"""

from collections import Counter
from typing import Any, Dict, List

import requests

import config

GITHUB_API_URL = "https://api.github.com"


class GitHubError(Exception):
    """Raised when the GitHub API cannot be used (bad username, rate limit...)."""


def _headers() -> Dict[str, str]:
    """Standard headers for the GitHub REST API."""
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    token = config.settings.github_token.strip()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _get(url: str, params: Dict[str, Any] = None) -> requests.Response:
    """GET a GitHub API endpoint with a timeout."""
    return requests.get(
        url,
        headers=_headers(),
        params=params,
        timeout=config.settings.github_timeout_seconds,
    )


def _explain(response: requests.Response, username: str) -> None:
    """Turn GitHub API error codes into friendly GitHubError messages."""
    if response.status_code == 404:
        raise GitHubError(f"GitHub user '{username}' was not found.")
    if response.status_code == 403 and response.headers.get("X-RateLimit-Remaining") == "0":
        raise GitHubError(
            "GitHub API rate limit reached. Add a GITHUB_TOKEN to your .env "
            "file to raise the limit to 5000 requests/hour."
        )
    raise GitHubError(
        f"GitHub API request failed with status {response.status_code}. "
        "Please try again in a moment."
    )


def fetch_profile(username: str) -> Dict[str, Any]:
    """
    Fetch a user's profile + repositories and return a compact summary dict.

    The dict contains structured stats plus an `evidence_text` block that
    is fed directly to the GitHub Evidence Agent.
    """
    username = (username or "").strip().lstrip("@").rstrip("/")
    if not username or any(char.isspace() for char in username):
        raise GitHubError("Please provide a valid GitHub username.")

    # 1) Basic profile information.
    response = _get(f"{GITHUB_API_URL}/users/{username}")
    if response.status_code != 200:
        _explain(response, username)
    user = response.json()

    # 2) Public repositories, most recently pushed first (up to 100).
    response = _get(
        f"{GITHUB_API_URL}/users/{username}/repos",
        params={"per_page": 100, "sort": "pushed"},
    )
    if response.status_code != 200:
        _explain(response, username)
    repos = response.json()

    return build_profile_summary(user, repos)


def build_profile_summary(user: Dict[str, Any], repos: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Turn raw GitHub API data into a compact, LLM-friendly summary.

    This is a pure function (no network calls), which keeps it easy to
    test. `repos` is the raw list from /users/{u}/repos.
    """
    # Ignore forks — they say little about what the person actually built.
    own_repos = [repo for repo in repos if not repo.get("fork")]

    # Count primary languages across the developer's own repositories.
    language_counts = Counter()
    for repo in own_repos:
        if repo.get("language"):
            language_counts[repo["language"]] += 1

    # Pick the most impressive repos: stars first, recent activity second.
    sorted_repos = sorted(
        own_repos,
        key=lambda repo: (repo.get("stargazers_count", 0), repo.get("pushed_at", "")),
        reverse=True,
    )
    top_repos = sorted_repos[: config.settings.github_max_repos]

    total_stars = sum(repo.get("stargazers_count", 0) for repo in own_repos)
    total_forks = sum(repo.get("forks_count", 0) for repo in own_repos)
    topics = sorted({topic for repo in own_repos for topic in repo.get("topics", [])})

    profile: Dict[str, Any] = {
        "username": user.get("login", ""),
        "name": user.get("name") or "",
        "bio": user.get("bio") or "",
        "followers": user.get("followers", 0),
        "public_repos": user.get("public_repos", 0),
        "account_created": user.get("created_at", ""),
        "total_stars": total_stars,
        "total_forks": total_forks,
        "languages": [lang for lang, _ in language_counts.most_common()],
        "topics": topics,
        "top_repos": [
            {
                "name": repo.get("name", ""),
                "description": repo.get("description") or "",
                "language": repo.get("language") or "",
                "stars": repo.get("stargazers_count", 0),
                "forks": repo.get("forks_count", 0),
                "topics": repo.get("topics", []),
                "last_pushed": (repo.get("pushed_at") or "")[:10],
                "url": repo.get("html_url", ""),
            }
            for repo in top_repos
        ],
    }

    profile["evidence_text"] = _build_evidence_text(profile)
    return profile


def _build_evidence_text(profile: Dict[str, Any]) -> str:
    """Render the profile dict as compact text for the LLM prompt."""
    lines = [
        f"GitHub username: {profile['username']}",
        f"Name: {profile['name'] or 'not set'}",
        f"Bio: {profile['bio'] or 'not set'}",
        f"Followers: {profile['followers']} | Public repos: {profile['public_repos']} "
        f"(own, non-fork repos analysed: {len(profile['top_repos'])} of the most starred)",
        f"Total stars received: {profile['total_stars']} | Total forks received: {profile['total_forks']}",
        f"Account created: {profile['account_created'][:10]}",
        f"Languages used across own repos: {', '.join(profile['languages']) or 'none detected'}",
        f"Repo topics: {', '.join(profile['topics']) or 'none'}",
        "Most notable repositories:",
    ]
    for repo in profile["top_repos"]:
        topics = ", ".join(repo["topics"]) or "-"
        description = repo["description"] or "no description"
        lines.append(
            f"- {repo['name']} ({repo['language'] or 'unknown'}, "
            f"{repo['stars']} stars, {repo['forks']} forks, last push {repo['last_pushed']}): "
            f"{description} [topics: {topics}]"
        )
    return "\n".join(lines)
