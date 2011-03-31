#! /bin/sh

usage='USAGE: gcode-upload.sh VERSION USERNAME GCODE-PASSWORD

The gcode password is available from http://code.google.com/hosting/settings;
it is *not* your google account password.
'

if test $# != 3; then
    echo "$usage"
    exit 1
fi

if test ! -f common/googlecode_upload.py; then
    echo "download googlecode_upload.py from"
    echo "  http://support.googlecode.com/svn/trunk/scripts/googlecode_upload.py"
    echo "and place it in common/"
    exit 1
fi

VERSION="$1"
USERNAME="$2"
PASSWORD="$3"

findfile() {
    local file="$1"
    test -f "dist/$file" && echo "dist/$file"
    test -f "master/dist/$file" && echo "master/dist/$file"
    test -f "slave/dist/$file" && echo "slave/dist/$file"
    test -f "$file" && echo "$file"
}

findlabels() {
    local file="$1"
    local labels=Featured
    if test "`echo $file | sed 's/.*\.asc/Signature/'`" = "Signature"; then
        labels="$labels,Signature"
    fi
    if test "`echo $file | sed 's/.*\.tar.gz.*/Tar/'`" = "Tar"; then
        labels="$labels,OpSys-POSIX"
    else
        labels="$labels,OpSys-Win"
    fi
    echo $labels
}

i=0
for file in {buildbot,buildbot-slave}-$VERSION.{tar.gz,zip}{,.asc}; do
    if test $i = 0; then
        i=1
        continue
    fi
    labels=`findlabels "$file"`
    file=`findfile "$file"`
    echo "Uploading $file with labels $labels"
        python common/googlecode_upload.py \
            -w $PASSWORD \
            -u $USERNAME \
            -p buildbot \
            -s `basename $file` \
            --labels=$labels \
            "$file"
done
