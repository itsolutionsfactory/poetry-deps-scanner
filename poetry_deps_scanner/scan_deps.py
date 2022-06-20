#!/usr/bin/env python
import concurrent
import sys
from concurrent.futures.thread import ThreadPoolExecutor
from typing import Iterable

import toml
from packaging.version import Version, parse
from pypi_simple import PYPI_SIMPLE_ENDPOINT, DistributionPackage, PyPISimple


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
                exc_name = type(exc).__name__
                message = str(exc)
                if message:
                    message = f" ({message})"
                data = f"e {package_name} generated an exception: {exc_name}{message}"
            if data:
                updates.append(data)

    if not updates:
        print("Everything up to date.")
    else:
        print("\n".join(sorted(updates)))


def get_direct_dependencies(pyproject_file_path: str) -> set[str] | None:
    if pyproject_file_path is None:
        return None
    pyproject = toml.load(pyproject_file_path)
    poetry = pyproject.get("tool", {}).get("poetry", {})
    if not poetry:
        return None
    dependencies = {
        dep_name.lower() for dep_name in poetry.get("dependencies", {}).keys()
    }
    dependencies.update(
        dep_name.lower() for dep_name in poetry.get("dev-dependencies", {}).keys()
    )
    return dependencies


def print_package_report(package: dict, dependencies: Iterable[str]) -> str | None:
    name = package["name"]
    version = package["version"]

    if dependencies is None:
        transitive_or_direct = ""
    elif name.lower() in dependencies:
        transitive_or_direct = "direct "
    else:
        transitive_or_direct = "trans. "

    url = get_url(package)
    if url is None:
        source = "git? "
        return f"{transitive_or_direct}{source} {name}: Couldn't compare versions."

    with PyPISimple(url) as client:
        project = client.get_project_page(name)

    if url == PYPI_SIMPLE_ENDPOINT:
        source = "pypi "  # space intentional to maintain alignment
    else:
        source = "devpi"

    if not project:
        return f"{transitive_or_direct}{source} {name}: Couldn't find project."

    versions = get_versions(project.packages)
    latest = get_latest_version(version, versions)

    if version != latest:
        return f"{transitive_or_direct}{source} {name}: current={version} -> latest={latest}"
    return None


def get_url(package: dict) -> str | None:
    source = package.get("source")
    if not source:
        return PYPI_SIMPLE_ENDPOINT

    if source.get("type") == "git":
        return None

    return source["url"]


def get_versions(packages: Iterable[DistributionPackage]) -> list[Version]:
    return [parse(package.version) for package in packages]


def get_latest_version(current_version: str, versions: Iterable[Version]) -> str:
    current_version = parse(current_version)
    if current_version.is_prerelease:
        return str(max(versions))
    else:
        # Filter out pre-releases if current version is not one
        return str(max(filter(is_public_version, versions)))


def is_public_version(version: Version):
    return not version.is_prerelease and not version.is_devrelease


class ScanDepsError(Exception):
    pass


class UnsupportedApiError(ScanDepsError):
    pass


if __name__ == "__main__":
    main()
