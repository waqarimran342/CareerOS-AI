---
kind: external_dependency
name: GitHub REST API — public profile and repository evidence source
slug: github-rest-api
category: external_dependency
category_hints:
    - vendor_identity
    - client_constraint
scope:
    - '**'
---

### Identity & role
- Public GitHub data (profile, repositories, languages, stars, topics) is fetched via the GitHub REST API to provide objective coding evidence alongside resume claims.

### Integration shape
- `src/github_service.py` queries the public profiles/repos endpoints, excludes forks, aggregates language counts, and produces a compact `evidence_text` consumed by the GitHub Evidence Agent.
- Rate limits and timeouts are controlled by `GITHUB_TIMEOUT` and `GITHUB_MAX_REPOS` in `.env`.

### Client constraint
- Without a token, rate limiting is tight enough to block repeated demo runs; provision a fine-grained PAT from `https://github.com/settings/tokens` (no extra scopes needed for public data).