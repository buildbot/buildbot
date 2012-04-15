#! /bin/bash

REVRANGE="$1..HEAD"
TEST='buildbot.test buildslave.test'

# some colors
# plain
_ESC=$'\e'
GREEN="$_ESC[0;32m"
MAGENTA="$_ESC[0;35m"
RED="$_ESC[0;31m"
YELLOW="$_ESC[1;33m"
NORM="$_ESC[0;0m"

if [ $# -eq 0 ]; then
    echo "USAGE: common/validate.sh oldrev"
    echo "  This script will test a set of patches (oldrev..HEAD) for basic acceptability as a patch"
    echo "  Run it in an activated virtualenv with the current Buildbot installed, as well as"
    echo "      sphinx, pyflakes, mock, and coverage."
    echo "To use a different directory for tests, pass TRIALTMP=/path as an env variable"
    exit 1
fi

status() {
    echo ""
    echo "${YELLOW}-- ${*} --${NORM}"
}

ok=true
not_ok() {
    ok=false
    echo "${RED}** ${*} **${NORM}"
}

check_long_lines() {
    # only check python files
    local long_lines=false
    for f in $(git diff --name-only --stat "$REVRANGE" | grep '.py$'); do
        # don't try to check removed files
        [ ! -f "$f" ] && continue
        if [ $(git diff "$REVRANGE" $f | grep -c '+.{80}') != 0 ]; then
            echo " $f"
            long_lines=true
        fi
    done
    $long_lines
}

if ! git diff --no-ext-diff --quiet --exit-code; then
    not_ok "changed files in working copy"
    exit 1
fi

echo "${MAGENTA}Validating the following commits:${NORM}"
git log "$REVRANGE" --pretty=oneline || exit 1

status "checking formatting"
git diff "$REVRANGE" | grep -q $'+.*\t' && not_ok "$REVRANGE adds tabs"
check_long_lines && not_ok "$REVRANGE adds long lines"

status "running tests"
if [ -n "${TRIALTMP}" ]; then
    echo rm -rf ${TRIALTMP}
    TEMP_DIRECTORY_OPT="--temp-directory ${TRIAL_TMP}"
fi

coverage erase || exit 1
coverage run --rcfile=.coveragerc \
    sandbox/bin/trial --reporter summary ${TEMP_DIRECTORY_OPT} ${TEST} \
    || not_ok "tests failed"

status "running pyflakes"
make pyflakes || not_ok "failed pyflakes"

status "coverage report"
coverage report > covreport || exit 1
head -n2 covreport || exit 1
tail -n1 covreport || exit 1
rm covreport || exit 1

status "building docs"
make -C master/docs VERSION=latest clean html || not_ok "docs failed"

echo ""
if $ok; then
    echo "${GREEN}GOOD!${NORM}"
    exit 0
else
    echo "${RED}NO GOOD!${NORM}"
    exit 1
fi
