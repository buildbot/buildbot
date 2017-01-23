#!/bin/bash
function status()
{
    _ESC=$'\e'
    LTCYAN="$_ESC[1;36m"
    NORM="$_ESC[0;0m"

    echo ""
    echo "${LTCYAN}-- ${*} --${NORM}"
}

function newshell()
{
    echo "I will launch a new shell. When you are done, just exit the shell"
    echo "and I will continue the process"
    bash
    echo "ok lets continue"
}

function unittests()
{
    status run the whole test suite as a double check
    find . -name \*.pyc -exec rm {} \;
    trial --reporter=text buildbot_worker buildbot
    if [[ $? != 0 ]]
    then
        echo "Oups.. the tests are failing, better resolve them now before the big autopep8 work"
        newshell
    fi
}
if [ $# -eq 0 ]; then
    echo "USAGE: common/merge_and_pep8.sh <refs/to/master>"
    echo "  This script will merge your branch to master"
    echo "  and apply pep8"
    echo "Run this if you want to contribute a branch based on pre-autopep8 rework"
    exit 1
fi

MASTER=$1
PREPEP8=`git log $MASTER --grep "PRE_PEP8_COMMIT" --pretty="format:%H"`
POSTPEP8=`git log $MASTER --grep "POST_PEP8_COMMIT" --pretty="format:%H"`

status "merging against last commit before autopep8"

git merge $PREPEP8
if [[ $? != 0 ]]
then
    echo "Please fix the merge conflicts between your branch, and last commit before autopep8!"
    newshell
fi

status "merging against first commit after autopep8 and take our version when there are conflicts"
git merge $POSTPEP8
# autopep8 takes 1h30 to run on the whole codebase, so let git resolve the obvious merge conflicts.
# using -s recursive -x ours works at chunk level, which proved not to work for nine -> master merge
if [[ $? != 0 ]]
then
    status "resolve conflicts by checking out ours file"
    git status --porcelain |egrep "^DU" | awk '{print $2}' | xargs git rm
    git status --porcelain |egrep "^UU" | awk '{print $2}' | xargs git checkout --ours
    git status --porcelain |egrep "^UU" | awk '{print $2}' | xargs git add
    git commit --no-edit
fi

unittests

status "re-apply autopep8 on the files modified by our branch"
git diff --name-only $POSTPEP8 |
(
    # there is no real use of displaying output of autopep8
    # so we just display a simple progress status
    FILES=()
    while read filename; do
      FILES+=($filename)
    done
    n=0
    for filename in ${FILES[@]}; do
        n=$(($n + 1))
        echo -n $(($n * 100 / ${#FILES[@]}))%
        echo " processing $filename"
        echo "$filename" | bash common/style_check_and_fix.sh >&/dev/null
    done
)
git commit -s -a -m "re-auto-pep8"

unittests

status "finally merge to latest version of master"
git merge $MASTER
