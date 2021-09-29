from dataclasses import dataclass
from pathlib import Path
from typing import List
from urllib.parse import urlparse
import argparse
import itertools
import json
import os
import requests
import sys
import time

@dataclass
class Fork:
    user:     str
    repo:     str
    url:      str
    http_url: str
    git_url:  str
    ssh_url:  str
    forks:    int
    stars:    int

    @classmethod
    def parse(cls, j):
        return cls(
            user=j["owner"]["login"],
            repo=j["name"],
            url=j["html_url"],
            http_url=j["clone_url"],
            git_url=j["git_url"],
            ssh_url=j["ssh_url"],
            stars=j["stargazers_count"],
            forks=j["forks_count"],
        )

def await_rate_limit(auth=()):
    r = requests.get("https://api.github.com/rate_limit", auth=auth)
    r.raise_for_status()
    j = r.json()
    core = j["resources"]["core"]
    if core["remaining"] == 0:
        reset = min(3600, core["reset"] - time.time() + 5)
        time.sleep(min(3600, core["reset"] - time.time() + 5))

def is_rate_limited(r):
    return r.headers.get("X-RateLimit-Remaining") == "0"

def fetch(url, auth=()):
    for i in range(3):
        r = requests.get(url, auth=auth)
        if r.status_code == 200:
            break
        if r.status_code == 403 and is_rate_limited(r):
            await_rate_limit(auth=auth)
        else:
            r.raise_for_status()
    else:
        r.raise_for_status()
    return r

def get_forks(user, repo, auth=()):
    await_rate_limit(auth=auth)
    r = fetch(f"https://api.github.com/repos/{user}/{repo}", auth=auth)
    j = r.json()
    yield Fork.parse(j)

    if not j.get('forks_count'):
        return

    for page in itertools.count():
        r = fetch(f"https://api.github.com/repos/{user}/{repo}/forks?page={page}", auth=auth)
        j = r.json()
        if not j:
            break
        for item in j:
            yield Fork.parse(item)
        if is_rate_limited(r):
            await_rate_limit(auth=auth)

def get_forks_recursive(user, repo, auth=()):
    fetched = set()
    yielded = set()
    queue = [(user, repo)]
    while queue:
        user, repo = queue.pop()
        fetched.add((user, repo))
        for fork in get_forks(user, repo, auth=auth):
            fork_key = (fork.user, fork.repo)
            if fork.forks and fork_key not in fetched:
                queue.append(fork_key)
            if fork_key not in yielded:
                yield fork
                yielded.add(fork_key)

def parse_url(url):
    if not "://" in url:
        url = f"https://{url}"
    p = urlparse(url)
    if p.netloc != "github.com":
        print(f"[!] skipping unknown host: {url}", file=sys.stderr)
        return None, None
    path = p.path.strip("/")
    user, repo, *extra = path.split("/")
    return user, repo

def build_config(args):
    os.makedirs(args.path, exist_ok=True)
    auth = tuple(args.auth.split(':', 1)) if args.auth else ()

    fpath = Path(args.path)
    forks = []
    for url in args.urls:
        user, repo = parse_url(url)
        if not repo:
            continue
        if args.recursive:
            fork_gen = get_forks_recursive(user, repo, auth=auth)
        else:
            fork_gen = get_forks(user, repo, auth=auth)
        for fork in fork_gen:
            forks.append(fork)
            if args.verbose:
                print(fork)
    forks.sort(key=lambda x: x.stars, reverse=True)

    config = {
        "name": args.name,
        "repos": [],
    }
    repos = config["repos"]
    for fork in forks:
        repos.append({
            "path": str(fpath / fork.user / fork.repo),
            "name": f"{fork.user}/{fork.repo}",
            "revisions": ["HEAD"],
            "metadata": {
                "remote": fork.http_url,
                "github": fork.url,
            },
        })
    with open(fpath / "livegrep.json", "w") as f:
        json.dump(config, f, indent=4)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('path', help='output directory')
    parser.add_argument('name', help='livegrep name')
    parser.add_argument('urls', help='github urls', nargs='+')
    parser.add_argument('--auth', help='http basic auth, "user:pass"')
    parser.add_argument('-r', '--recursive', help='follow forks recursively', action='store_true')
    parser.add_argument('-v', '--verbose',   help='more verbose output', action='store_true')
    args = parser.parse_args()
    build_config(args)
