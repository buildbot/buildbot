#!/bin/bash
# Generate the requirements files from uv.lock
set -e

cd "$(dirname "$0")/.."

uv_export() {
    uv export --quiet --frozen --no-hashes "$@"
}

uv_export --no-group docs -o requirements-ci.txt
uv_export --only-group docs --no-emit-workspace -o requirements-cidocs.txt
uv_export --only-group db -o requirements-cidb.txt
uv_export --no-group docs --group pyinstaller -o requirements-ci-pyinstaller.txt
uv_export --all-extras --all-groups --project=worker --no-emit-project -o requirements-ciworker.txt
