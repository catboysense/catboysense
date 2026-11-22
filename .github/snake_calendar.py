#!/usr/bin/env python3
"""Builds the contribution calendar that the snake eats.

GitHub's own calendar leaves out commits made in forks, so most of the owner's work never shows
up on it. This script takes the official one-year calendar, adds the owner's commits from public
forks, recomputes the four colour levels, and prints the result in the GraphQL response shape
that Platane/snk reads. The grid keeps the full year, so the snake stays as wide as the cards.

usage: GH_TOKEN=... python3 snake_calendar.py OWNER > calendar.json
"""
import json
import os
import sys
import urllib.request

API = "https://api.github.com/graphql"
LEVELS = ["NONE", "FIRST_QUARTILE", "SECOND_QUARTILE", "THIRD_QUARTILE", "FOURTH_QUARTILE"]


def gql(query, **variables):
    req = urllib.request.Request(
        API,
        data=json.dumps({"query": query, "variables": variables}).encode(),
        headers={"Authorization": "bearer " + os.environ["GH_TOKEN"],
                 "Content-Type": "application/json", "User-Agent": "profile-snake"})
    with urllib.request.urlopen(req, timeout=60) as r:
        body = json.load(r)
    if body.get("errors"):
        raise RuntimeError(body["errors"][0]["message"])
    return body["data"]


def fork_commit_days(user, since):
    """Author dates (YYYY-MM-DD, in the commit's own time zone) of the owner's commits in public forks."""
    days = []
    for repo in user["repositoriesContributedTo"]["nodes"]:
        if not repo["isFork"] or repo["isPrivate"]:
            continue
        cursor = None
        try:
            while True:
                data = gql("""query($o: String!, $n: String!, $id: ID!, $since: GitTimestamp!, $after: String) {
                    repository(owner: $o, name: $n) { defaultBranchRef { target { ... on Commit {
                      history(first: 100, author: {id: $id}, since: $since, after: $after) {
                        pageInfo { hasNextPage endCursor } nodes { authoredDate } } } } } } }""",
                           o=repo["owner"]["login"], n=repo["name"], id=user["id"], since=since, after=cursor)
                ref = data["repository"]["defaultBranchRef"]
                if not ref:
                    break
                history = ref["target"]["history"]
                days += [c["authoredDate"][:10] for c in history["nodes"]]
                if not history["pageInfo"]["hasNextPage"]:
                    break
                cursor = history["pageInfo"]["endCursor"]
        except (RuntimeError, OSError) as e:  # one broken fork must not cost the whole snake
            print(f"skipped {repo['owner']['login']}/{repo['name']}: {e}", file=sys.stderr)
    return days


def main():
    owner = sys.argv[1]
    user = gql("""query($login: String!) { user(login: $login) { id
        contributionsCollection { contributionCalendar { weeks { contributionDays { date weekday contributionCount } } } }
        repositoriesContributedTo(first: 100, includeUserRepositories: true,
          contributionTypes: [COMMIT, PULL_REQUEST, REPOSITORY]) { nodes { owner { login } name isFork isPrivate } } } }""",
               login=owner)["user"]
    weeks = [w["contributionDays"] for w in user["contributionsCollection"]["contributionCalendar"]["weeks"]]
    counts = {d["date"]: d["contributionCount"] for w in weeks for d in w}

    extra = fork_commit_days(user, weeks[0][0]["date"] + "T00:00:00Z")
    for day in extra:
        if day in counts:
            counts[day] += 1

    active = sorted(counts[d["date"]] for w in weeks for d in w if counts[d["date"]] > 0)

    def quantile(p):
        return active[min(len(active) - 1, int(p * len(active)))] if active else 0

    edges = [quantile(.25), quantile(.5), quantile(.75)]

    def level(c):
        return 0 if c == 0 else 1 + sum(c > e for e in edges)

    out = {"data": {"user": {"contributionsCollection": {"contributionCalendar": {"weeks": [
        {"contributionDays": [{"date": d["date"], "weekday": d["weekday"], "contributionCount": counts[d["date"]],
                               "contributionLevel": LEVELS[level(counts[d["date"]])]} for d in w]} for w in weeks]}}}}}
    json.dump(out, sys.stdout)
    print(f"weeks: {len(weeks)}, active days: {len(active)}, contributions: {sum(active)} "
          f"(of them {len(extra)} commits from forks)", file=sys.stderr)


if __name__ == "__main__":
    main()
