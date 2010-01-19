#! /bin/sh

# Make a source distribution, and verify that all files git knows about are
# also in the source dist

if ! test -d buildbot || ! test -d docs; then
    echo "not in the buildbot base dir"
    exit 1
fi

test -d dist || mkdir dist

existing=`ls -1 dist/ 2>/dev/null`
if test -n "$existing"; then
    echo "dist files already exist:"
    echo $existing
    echo "OK to delete? [Y/n] "
    read YN
    if test -n "$YN" && test "$YN" != "y"; then
        exit 1
    fi
    rm dist/*
fi

python setup.py sdist || exit 1

tar -ztf dist/*.tar.gz > distfiles || exit 1

for f in `git ls-files`; do
    echo $f | grep -q "\.git" && continue
    echo $f | grep -q "^docs/PyCon" && continue
    if ! grep -q $f distfiles; then
        echo "NOT FOUND: $f";
    fi
done

rm distfiles
