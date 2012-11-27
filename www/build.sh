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

VERSION=$(cd $BASEDIR/../master; python -c 'import buildbot; print buildbot.version')

echo "Building buildbot-www $VERSION with $PROFILE to $DISTDIR."

echo -n "Cleaning old files..."
rm -rf "$DISTDIR"
echo " Done"

echo "Rebuilding Buildbot HAML templates..."
for haml in `find "$SRCDIR/lib" -name '*.haml'`; do
    echo "$haml"
    NODE_PATH="$SRCDIR" node "$BASEDIR/src/hamlcc/lib/hamlcc.js" $haml
done

if [ "$1" = "--haml-only" ]; then
    exit 0
else
    echo "NOTE: use ./build.sh --haml-only to stop here"
fi

echo "Running $TOOLSDIR/build.sh..."
( cd "$TOOLSDIR" && ./build.sh --profile "$PROFILE" --releaseDir "$DISTDIR") || exit 1

echo -n "Copying index.html..."
cp "$SRCDIR/index.html" "$DISTDIR/index.html"
echo " Done"

echo -n "Removing uncompressed/consoleStripped files..."
find "$DISTDIR" \( -name '*.uncompressed.js' -o -name '*.consoleStripped.js' \) -exec rm \{} \;
echo " Done"

echo -n "Removing un-compiled haml files..."
find "$DISTDIR" -name '*.haml' -exec rm \{} \;
echo " Done"

# misc cleanup
rm -f "$DISTDIR/build-report.txt"

echo -n "Writing version"
echo $VERSION > "$DISTDIR/buildbot-version.txt"
echo " Done"

echo -n "Enumerating built files..."
(cd "$BASEDIR"; find built -type f ) > "$DISTDIR/file-list.txt"
echo " Done"

echo "Building sdist tarball..."
( cd "$BASEDIR"; python setup.py sdist )

echo "Build complete"
