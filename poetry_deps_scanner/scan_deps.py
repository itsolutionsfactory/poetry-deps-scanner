#!/usr/bin/env python
from __future__ import annotations

import concurrent
import enum
import sys
from concurrent.futures.thread import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Iterable
from urllib.parse import urlparse

import prettytable
import toml
from packaging.version import Version, parse
from prettytable import PrettyTable
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
    table = PrettyTable(["Name", "Type", "Source", "Message"])
    row_count = 0

    with ThreadPoolExecutor() as executor:
        future_to_package = {
            executor.submit(get_display_package, package, direct_dependencies): package[
                "name"
            ]
            for package in packages
        }
        for future in concurrent.futures.as_completed(future_to_package):
            package_name = future_to_package[future]
            try:
                display_package: DisplayPackage = future.result()
                if display_package.should_display():
                    table.add_row(display_package.to_row())
                    row_count += 1
            except Exception as exc:
                exc_name = type(exc).__name__
                message = str(exc)
                if message:
                    message = f"{exc_name} ({message})"
                else:
                    message = exc_name
                table.add_row([package_name, "error", "", message])
                row_count += 1

    table.set_style(prettytable.SINGLE_BORDER)
    table.border = False
    table.preserve_internal_border = True
    table.align = "l"
    table.sortby = "Type"
    if row_count == 0:
        print("Everything up to date.")
    else:
        print(table)


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


def get_display_package(package: dict, dependencies: Iterable[str]) -> DisplayPackage:
    name = package["name"]
    version = package["version"]
    display_package = DisplayPackage(name=name, current_version=version)

    if dependencies is None:
        display_package.transitive_or_direct = TransitiveOrDirect.UNKNOWN
    elif name.lower() in dependencies:
        display_package.transitive_or_direct = TransitiveOrDirect.DIRECT
    else:
        display_package.transitive_or_direct = TransitiveOrDirect.TRANSITIVE

    url, can_fetch = get_url(package)
    display_package.source = url
    if not can_fetch:
        display_package.error = "Couldn't compare versions."
        return display_package

    with PyPISimple(url) as client:
        project = client.get_project_page(name)

    if not project:
        display_package.error = "Couldn't find project."
        return display_package

    versions = get_versions(project.packages)
    display_package.latest_version = get_latest_version(version, versions)

    return display_package


def get_url(package: dict) -> tuple[str, bool]:
    source = package.get("source")
    can_fetch = True
    if not source:
        return PYPI_SIMPLE_ENDPOINT, can_fetch

    if source.get("type") == "git":
        can_fetch = False

    return source["url"], can_fetch


def get_versions(packages: Iterable[DistributionPackage]) -> list[Version]:
    return [parse(package.version) for package in packages if package.version]


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


class TransitiveOrDirect(enum.Enum):
    TRANSITIVE = "trans."
    DIRECT = "direct"
    UNKNOWN = ""


@dataclass
class DisplayPackage:
    name: str
    transitive_or_direct: TransitiveOrDirect = TransitiveOrDirect.UNKNOWN
    source: str = ""
    current_version: str = ""
    latest_version: str = ""
    error: str = ""

    def __str__(self) -> str:
        return f"{self.transitive_or_direct.value}{self.domain} {self.name}: {self.message}"

    @property
    def versions(self):
        return f"current={self.current_version} -> latest={self.latest_version}"

    @property
    def message(self):
        if self.error:
            return self.error
        return self.versions

    @property
    def domain(self):
        return urlparse(self.source).netloc

    def to_row(self) -> list[str]:
        return [self.name, self.transitive_or_direct.value, self.domain, self.message]

    def should_display(self) -> bool:
        return bool(self.error) or self.current_version != self.latest_version


if __name__ == "__main__":
    main()
