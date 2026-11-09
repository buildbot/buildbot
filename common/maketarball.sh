#!/bin/bash
set -e
pkg=$1
(
    cd ${pkg}
    rm -rf MANIFEST dist

    uv build --out-dir dist
)
cp ${pkg}/dist/* dist/
