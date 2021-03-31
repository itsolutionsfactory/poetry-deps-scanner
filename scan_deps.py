import sys
from concurrent.futures.thread import ThreadPoolExecutor
from typing import Iterable

import requests
import toml
from requests import HTTPError
from semver import Version


def main():
    if len(sys.argv) != 2:
        script_name = sys.argv[0]
        print(f"Usage: {script_name} <lock file path>")
        sys.exit(1)
    filepath = sys.argv[1]
    lock = get_lock_content(filepath)
    packages = lock["package"]
    with ThreadPoolExecutor() as executor:
        for package in packages:
            executor.submit(print_package_report, package)


def print_package_report(package):
    name = package["name"]
    version = package["version"]
    url, is_pypi = get_url(package)
    res = requests.get(url, headers={"Accept": "application/json"})
    try:
        res.raise_for_status()
    except HTTPError as e:
        print(f"Error in network query for {name}: {e}")

    json = res.json()
    if is_pypi:
        latest = json["info"]["version"]
        source = "p"
    else:
        versions = json["result"].keys()
        latest = get_latest_version(versions)
        source = "d"
    if version != latest:
        print(f"{source} {name}: current={version} -> latest={latest}")


def get_url(package: dict) -> (str, bool):
    name = package["name"]
    source_url = package["source"]["url"]
    if "https://devpi.itsf.io/root/pypi" in source_url:
        return f"https://pypi.org/pypi/{name}/json", True

    source_url = source_url.replace("+simple", "")  # type: str
    if not source_url.endswith("/"):
        source_url += "/"
    return source_url + name, False


def get_lock_content(filepath):
    with open(filepath) as f:
        lock = toml.load(f)
    return lock


def get_latest_version(versions: Iterable[str]) -> str:
    try:
        versions = [Version.parse(version) for version in versions]
    except ValueError:
        return "couldn't determine: Not all versions are valid semver"
    return str(max(versions))


if __name__ == "__main__":
    main()
