#!/usr/bin/env python
import concurrent
import sys
from concurrent.futures.thread import ThreadPoolExecutor
from typing import Dict, Iterable, Optional, Set

import requests
import toml
from semver import Version


def main():
    if len(sys.argv) > 3 or len(sys.argv) < 2:
        script_name = sys.argv[0]
        print(f"Usage: {script_name} <path/to/poetry.lock> [<path/to/pyproject.toml>]")
        sys.exit(1)
    if len(sys.argv) == 3:
        pyproject_file_path = sys.argv[2]
    else:
        pyproject_file_path = None

    direct_dependencies = get_direct_dependencies(pyproject_file_path)

    lock_file_path = sys.argv[1]
    lock = toml.load(lock_file_path)
    packages = lock["package"]
    updates = []

    with ThreadPoolExecutor() as executor:
        future_to_package = {
            executor.submit(
                print_package_report, package, direct_dependencies
            ): package["name"]
            for package in packages
        }
        for future in concurrent.futures.as_completed(future_to_package):
            package_name = future_to_package[future]
            try:
                data = future.result()
            except Exception as exc:
                data = f"e {package_name} generated an exception: {exc}"
            if data:
                updates.append(data)

    if not updates:
        print("Everything up to date.")
    else:
        print("\n".join(sorted(updates)))


def get_direct_dependencies(pyproject_file_path: str) -> Optional[Set[str]]:
    if pyproject_file_path is None:
        return None
    pyproject = toml.load(pyproject_file_path)
    poetry = pyproject.get("tool", {}).get("poetry", {})
    if not poetry:
        return None
    dependencies = set(
        dep_name.lower() for dep_name in poetry.get("dependencies", {}).keys()
    )
    dependencies.update(
        dep_name.lower() for dep_name in poetry.get("dev-dependencies", {}).keys()
    )
    return dependencies


def print_package_report(package: Dict, dependencies: Iterable[str]) -> Optional[str]:
    name = package["name"]
    version = package["version"]
    url, is_pypi = get_url(package)
    res = requests.get(url, headers={"Accept": "application/json"})
    res.raise_for_status()

    json = res.json()
    if is_pypi:
        latest = json["info"]["version"]
        source = "pypi "  # space intentional to maintain alignment
    else:
        versions = json["result"].keys()
        latest = get_latest_version(versions)
        source = "devpi"

    if dependencies is None:
        transitive_or_direct = ""
    elif name.lower() in dependencies:
        transitive_or_direct = "direct "
    else:
        transitive_or_direct = "trans. "

    if version != latest:
        return f"{transitive_or_direct}{source} {name}: current={version} -> latest={latest}"
    return None


def get_url(package: dict) -> (str, bool):
    name = package["name"]
    source = package.get("source")
    if not source:
        return f"https://pypi.org/pypi/{name}/json", True

    source_url = source["url"]
    if "https://devpi.itsf.io/root/pypi" in source_url:
        return f"https://pypi.org/pypi/{name}/json", True

    source_url = source_url.replace("+simple", "")  # type: str
    if not source_url.endswith("/"):
        source_url += "/"
    elif source_url.endswith("//"):
        source_url = source_url[:-1]
    return source_url + name, False


def get_latest_version(versions: Iterable[str]) -> str:
    try:
        versions = [Version.parse(version) for version in versions]
    except ValueError:
        return "couldn't determine: Not all versions are valid semver"
    return str(max(versions))


if __name__ == "__main__":
    main()
