#!/usr/bin/env python3
"""Gate of the public arxo registry — the only CI of this repository.

The registry is a store, not an evaluator: there is not a single line of
Law DSL semantics here, only integrity and immutability. The source of truth
for this file is the law-dsl monorepo (apps/registry/remote/); it arrives
here as a vendored copy via the exporter and is never edited by hand.

Three checks:

1. **Schema and addressing.** Every p/<name>/<version>.json is valid — against
   package-descriptor.schema.json when it declares descriptorFormat 0.2, and
   against the older LockedPackage shape (lockfile.schema.json) when it does
   not. Name/version match the path, registryId matches registry.json,
   resolverUri follows the registry://<id>/<name>/<version> convention. The
   version index p/<name>/versions.json must list exactly the versions that
   are actually published, and a descriptor's declared resources must have
   their bytes under r/<algo>/<hex>.
2. **Bytes.** The descriptor's contentHash == sha256 of the sibling
   p/<name>/<version>/package.lawir.json. Package bytes are canonical (§208),
   so hashing the downloaded file is all a consumer needs. When a source
   bundle is published (p/<name>/<version>/src/**), source.json next to it
   must list exactly the files present, each with a matching sha256 — no
   unlisted bytes, no dangling entries. The correspondence between sources
   and compiled CLIR is enforced by the monorepo gates before publication;
   this repository holds integrity, not semantics.
3. **Immutability** (with --base <git-ref>): the diff under p/ relative to
   the base may contain additions only. Modifying or deleting a published
   file fails; a bad version is fixed by publishing the next version. The
   one exception is p/<name>/versions.json: it is an index of what exists,
   not a publication, so a new release necessarily rewrites it.

Dependencies: python3 >= 3.9, jsonschema, git (for --base).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import jsonschema

ROOT = Path(__file__).resolve().parent


#: Index of published versions; rewritten by every release, hence mutable.
VERSIONS_FILE = "versions.json"


def legacy_validator() -> jsonschema.Draft202012Validator:
    schema = json.loads((ROOT / "lockfile.schema.json").read_text(encoding="utf-8"))
    return jsonschema.Draft202012Validator(
        {"$ref": "#/$defs/LockedPackage", "$defs": schema["$defs"]})


def descriptor_validator() -> jsonschema.Draft202012Validator:
    schema = json.loads((ROOT / "package-descriptor.schema.json").read_text(encoding="utf-8"))
    return jsonschema.Draft202012Validator(schema)


def versions_validator() -> jsonschema.Draft202012Validator:
    schema = json.loads((ROOT / "package-descriptor.schema.json").read_text(encoding="utf-8"))
    return jsonschema.Draft202012Validator(
        {"$ref": "#/$defs/PackageVersions", "$defs": schema["$defs"]})


def check_blobs(errors: list[str]) -> int:
    """Every r/<algo>/<hex> must hash to its own name: the consumer trusts the
    address, so a blob that does not match it is a silently wrong resource."""
    checked = 0
    for blob in sorted((ROOT / "r").rglob("*")):
        if not blob.is_file():
            continue
        algo, name = blob.parent.name, blob.name
        rel = blob.relative_to(ROOT)
        if algo != "sha256":
            errors.append(f"{rel}: unsupported digest directory {algo!r}")
            continue
        actual = hashlib.sha256(blob.read_bytes()).hexdigest()
        if actual != name:
            errors.append(f"{rel}: bytes hash to {actual}")
        checked += 1
    return checked


def check_versions_index(name: str, published: set[str], errors: list[str]) -> None:
    path = ROOT / "p" / name / VERSIONS_FILE
    rel = path.relative_to(ROOT)
    if not path.exists():
        # Legacy registries predate the index; a 0.2 consumer then cannot pick
        # "the latest stable" and must be told to name the version explicitly.
        return
    try:
        index = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        errors.append(f"{rel}: not JSON: {exc}")
        return
    for err in sorted(versions_validator().iter_errors(index), key=str):
        errors.append(f"{rel}: schema: {err.message}")
        return
    if index.get("name") != name:
        errors.append(f"{rel}: index names {index.get('name')!r}, path says {name!r}")
    listed = set(index.get("versions", []))
    for version in sorted(listed - published):
        errors.append(f"{rel}: lists {version}, which is not published")
    for version in sorted(published - listed):
        errors.append(f"{rel}: does not list published version {version}")


def check_immutability(base: str, errors: list[str]) -> None:
    proc = subprocess.run(
        ["git", "diff", "--name-status", base, "HEAD", "--", "p/"],
        cwd=ROOT, capture_output=True, text=True)
    if proc.returncode != 0:
        errors.append(f"immutability: git diff against {base!r} failed: "
                      f"{proc.stderr.strip()}")
        return
    for line in proc.stdout.splitlines():
        status, _, path = line.partition("\t")
        if Path(path).name == VERSIONS_FILE:
            continue
        if status[:1] != "A":
            errors.append(f"immutability: {path} — status {status}, "
                          "only additions are allowed under p/")


def check_source_bundle(version_dir: Path, rel: str, errors: list[str]) -> None:
    """src/ and source.json come and go together, and source.json must list
    exactly the files present — an unlisted byte is as much a defect as a
    dangling entry."""
    src_dir = version_dir / "src"
    listing_path = version_dir / "source.json"
    if not src_dir.exists() and not listing_path.exists():
        return
    if not listing_path.exists():
        errors.append(f"{rel}: src/ without source.json")
        return
    if not src_dir.exists():
        errors.append(f"{rel}: source.json without src/")
        return
    try:
        listing = json.loads(listing_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        errors.append(f"{rel}: source.json is not JSON: {exc}")
        return
    listed = {entry.get("path"): entry.get("sha256")
              for entry in listing.get("files", [])}
    actual = {"/".join(p.relative_to(src_dir).parts):
              hashlib.sha256(p.read_bytes()).hexdigest()
              for p in sorted(src_dir.rglob("*")) if p.is_file()}
    for path in sorted(set(listed) - set(actual)):
        errors.append(f"{rel}: source.json lists missing file src/{path}")
    for path in sorted(set(actual) - set(listed)):
        errors.append(f"{rel}: unlisted file src/{path}")
    for path in sorted(set(listed) & set(actual)):
        if listed[path] != actual[path]:
            errors.append(f"{rel}: src/{path} — sha256 {actual[path]}, "
                          f"source.json says {listed[path]}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--base", help="git ref to check immutability against "
                                       "(PR: branch base; push: previous commit)")
    args = parser.parse_args()

    errors: list[str] = []
    registry_id = json.loads((ROOT / "registry.json")
                             .read_text(encoding="utf-8"))["registryId"]
    legacy, modern = legacy_validator(), descriptor_validator()

    descriptors = [p for p in sorted((ROOT / "p").glob("*/*.json"))
                   if p.name != VERSIONS_FILE]
    published: dict[str, set[str]] = {}
    checked = 0
    for desc_path in descriptors:
        name, version = desc_path.parent.name, desc_path.stem
        rel = desc_path.relative_to(ROOT)
        try:
            desc = json.loads(desc_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            errors.append(f"{rel}: not JSON: {exc}")
            continue
        validator = modern if desc.get("descriptorFormat") else legacy
        for err in sorted(validator.iter_errors(desc), key=str):
            errors.append(f"{rel}: schema: {err.message}")
        if desc.get("name") != name or desc.get("version") != version:
            errors.append(f"{rel}: descriptor name/version "
                          f"({desc.get('name')}/{desc.get('version')}) do not match the path")
        if desc.get("registryId") != registry_id:
            errors.append(f"{rel}: registryId {desc.get('registryId')!r}, "
                          f"registry has {registry_id!r}")
        expected_uri = f"registry://{registry_id}/{name}/{version}"
        if desc.get("resolverUri") != expected_uri:
            errors.append(f"{rel}: resolverUri {desc.get('resolverUri')!r}, "
                          f"expected {expected_uri!r}")
        package_path = desc_path.parent / version / "package.lawir.json"
        if not package_path.exists():
            errors.append(f"{rel}: missing package bytes {package_path.relative_to(ROOT)}")
        else:
            digest = "sha256:" + hashlib.sha256(package_path.read_bytes()).hexdigest()
            if desc.get("contentHash") != digest:
                errors.append(f"{rel}: contentHash {desc.get('contentHash')}, "
                              f"actual bytes {digest}")
        if desc.get("worldHash"):
            world_path = desc_path.parent / version / "world.lawir.json"
            if not world_path.exists():
                errors.append(f"{rel}: worldHash declared, but "
                              f"{world_path.relative_to(ROOT)} is missing")
            else:
                digest = "sha256:" + hashlib.sha256(world_path.read_bytes()).hexdigest()
                if desc["worldHash"] != digest:
                    errors.append(f"{rel}: worldHash {desc['worldHash']}, actual bytes {digest}")
        for resource in desc.get("resources", []):
            digest = str(resource.get("contentHash", ""))
            algo, _, hex_digest = digest.partition(":")
            blob = ROOT / "r" / algo / hex_digest
            if not hex_digest or not blob.exists():
                errors.append(f"{rel}: resource {resource.get('id')!r} declares "
                              f"{digest}, but r/{algo}/{hex_digest} is missing")
        check_source_bundle(desc_path.parent / version, str(rel), errors)
        published.setdefault(name, set()).add(version)
        checked += 1

    # Bytes without a descriptor are a defect too: an unaddressable publication.
    for package_path in sorted((ROOT / "p").glob("*/*/package.lawir.json")):
        desc_path = package_path.parent.parent / f"{package_path.parent.name}.json"
        if not desc_path.exists():
            errors.append(f"{package_path.relative_to(ROOT)}: missing descriptor "
                          f"{desc_path.relative_to(ROOT)}")

    for name, versions in sorted(published.items()):
        check_versions_index(name, versions, errors)
    blobs = check_blobs(errors)

    if args.base:
        check_immutability(args.base, errors)

    for line in errors:
        print(f"FAIL {line}", file=sys.stderr)
    immut = f", immutability against {args.base}" if args.base else ""
    print(f"check_registry: {checked} publications, {blobs} resource blobs{immut} — "
          + ("FAIL" if errors else "PASS"))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
