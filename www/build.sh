#!/usr/bin/env bash

set -e

BASEDIR=$(cd $(dirname $0) && pwd)
SRCDIR="$BASEDIR/src"
TOOLSDIR="$SRCDIR/util/buildscripts"
DISTDIR="$BASEDIR/built"
PROFILE="$BASEDIR/profiles/buildbot.profile.js"

if [ ! -d "$TOOLSDIR" ]; then
    echo "Can't find Dojo build tools -- did you initialise submodules? (git submodule update --init --recursive)"
    exit 1
fi

VERSION=$(cd ../master; python -c 'import buildbot; print buildbot.version')

echo "Building buildbot-www $VERSION with $PROFILE to $DISTDIR."

echo -n "Cleaning old files..."
rm -rf "$DISTDIR"
echo " Done"

echo "Running $TOOLSDIR/build.sh..."
( cd "$TOOLSDIR" && ./build.sh --profile "$PROFILE" --releaseDir "$DISTDIR") || exit 1

echo -n "Copying index.html..."
cp "$SRCDIR/index.html" "$DISTDIR/index.html"
echo " Done"

echo -n "Removing uncompressed/consoleStripped files..."
find "$DISTDIR" \( -name '*.uncompressed.js' -o -name '*.consoleStripped.js' \) -exec rm \{} \;
rm -f "$DISTDIR/build-report.txt"
echo " Done"

echo -n "Writing version"
echo $VERSION > "$DISTDIR/buildbot-version.txt"
echo " Done"

echo -n "Enumerating built files..."
(cd "$BASEDIR"; find built -type f ) > built/file-list.txt
echo " Done"

echo "Building sdist tarball..."
( cd "$BASEDIR"; python setup.py sdist )

echo "Build complete"
