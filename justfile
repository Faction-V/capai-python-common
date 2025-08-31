set dotenv-load := true
set shell := ["bash", "-c"]

# list available commands
_default:
    @just --list

[doc('format the justfile(s)')]
[group('utils')]
fmt:
    @just --fmt --unstable -f justfile

[doc('Release a new version. Updates pyproject.toml version, git tags, and pushes changes.')]
[group('release')]
release version:
    #!/usr/bin/env bash
    poetry version {{ version }}
    git add pyproject.toml
    git commit -m "{{ version }}"
    git tag {{ version }}
    git push
    git push --tags
    poetry version
