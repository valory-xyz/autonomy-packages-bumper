import argparse
import urllib.request
import urllib.error
import os
import sys
import json
import base64

TARGET_FILE = "packages/packages.json"
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")

REPOS = [
    "valory-xyz/open-aea",
    "valory-xyz/open-autonomy",
    "valory-xyz/mech",
    "valory-xyz/mech-tools-dev",
    "valory-xyz/mech-client",
    "valory-xyz/mech-predict",
    "valory-xyz/mech-interact",
    "valory-xyz/trader",
    "valory-xyz/market-creator",
    "valory-xyz/IEKit",
    "valory-xyz/optimus",
    "valory-xyz/olas-sdk-starter",
    "valory-xyz/dev-template",
    "valory-xyz/academy-learning-service-template",
    "valory-xyz/meme-ooorr",
    "valory-xyz/governatooorr",
]


class Package:
    def __init__(self, name: str, hash: str, repo: str):
        self.name = name
        self.hash = hash
        self.repo = repo


def github_api(method: str, path: str, body: dict | None = None) -> dict | None:
    url = f"https://api.github.com{path}"
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("X-GitHub-Api-Version", "2022-11-28")
    if GITHUB_TOKEN:
        req.add_header("Authorization", f"Bearer {GITHUB_TOKEN}")
    if data:
        req.add_header("Content-Type", "application/json")

    try:
        with urllib.request.urlopen(req) as response:
            return json.loads(response.read().decode())
    except urllib.error.HTTPError as e:
        print(f"  GitHub API error {e.code}: {e.reason}", file=sys.stderr)
        print(f"  {e.read().decode()}", file=sys.stderr)
        return None
    except urllib.error.URLError as e:
        print(f"  Network error: {e.reason}", file=sys.stderr)
        return None


def fetch_packages(repo: str) -> dict | None:
    """Returns parsed JSON for packages/packages.json."""
    path = f"/repos/{repo}/contents/{TARGET_FILE}"
    result = github_api("GET", path)
    if result is None:
        return None
    content = base64.b64decode(result["content"]).decode()
    return json.loads(content)



def main():
    parser = argparse.ArgumentParser(description="Check and update local packages.json third-party hashes.")
    parser.add_argument("--dry-run", action="store_true", help="Print changes without writing to packages.json.")
    parser.add_argument("--verbose", action="store_true", help="Print logs.")
    args = parser.parse_args()

    def log(msg: str, **kwargs) -> None:
        if args.verbose:
            print(msg, **kwargs)

    published: dict[str, list[Package]] = {}
    checked_repos: list[str] = []

    for repo_name in REPOS:
        data = fetch_packages(repo_name)
        if data is None:
            log(f"ERROR No {repo_name} packages", file=sys.stderr)
            continue

        checked_repos.append(repo_name)
        log(f"INFO Parsing {repo_name} packages")
        for name, hash in data.get("dev", {}).items():
            published.setdefault(name, []).append(Package(name=name, hash=hash, repo=repo_name))
            log(f"INFO Found package in repo {repo_name}: {name}")

    # Open and read the local packages JSON file
    with open(TARGET_FILE) as f:
        packages = json.load(f)

    # Collect results
    updated: list[tuple[str, str, str, str]] = []   # (name, old_hash, new_hash, source_repo)
    collisions: list[tuple[str, list[str]]] = []    # (name, [claimant_repos])
    not_found: list[str] = []

    for name, hash in packages.get("third_party", {}).items():
        if name not in published:
            not_found.append(name)
        elif len(published[name]) > 1:
            collisions.append((name, [p.repo for p in published[name]]))
        elif hash != published[name][0].hash:
            new_hash = published[name][0].hash
            updated.append((name, hash, new_hash, published[name][0].repo))
            packages["third_party"][name] = new_hash

    print(f"Checked {len(checked_repos)} repo(s): {', '.join(checked_repos)}\n")

    if updated:
        print(f"Bumped {len(updated)} package(s):")
        for name, old_hash, new_hash, source_repo in updated:
            print(f"  {name}")
            print(f"    {old_hash} -> {new_hash} (from {source_repo})")
    else:
        print("All packages are up to date.")

    if collisions:
        print(f"\nSkipped {len(collisions)} package(s) due to name collision:")
        for name, claimants in collisions:
            print(f"  {name} — claimed by: {', '.join(claimants)}")

    if not_found:
        print(f"\n{len(not_found)} package(s) not found in any checked repo:")
        for name in not_found:
            print(f"  {name}")

    if not args.dry_run and updated:
        with open(TARGET_FILE, "w") as f:
            json.dump(packages, f, indent=4)


if __name__ == "__main__":
    main()
