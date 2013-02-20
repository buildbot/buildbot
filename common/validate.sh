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
    echo "      sphinx, pyflakes, mock, and so on"
    echo "To use a different directory for tests, pass TRIALTMP=/path as an env variable"
    exit 1
fi

status() {
    echo ""
    echo "${YELLOW}-- ${*} --${NORM}"
}

ok=true
problem_summary=""
not_ok() {
    ok=false
    echo "${RED}** ${*} **${NORM}"
    problem_summary="$problem_summary"$'\n'"${RED}**${NORM} ${*}"
}

check_tabs() {
    git diff "$REVRANGE" | grep -q $'+.*\t'
}

check_long_lines() {
    # only check python files
    local long_lines=false
    for f in $(git diff --name-only --stat "$REVRANGE" | grep '.py$'); do
        # don't try to check removed files
        [ ! -f "$f" ] && continue
        if [ $(git diff "$REVRANGE" $f | grep -E -c '^\+.{80}') != 0 ]; then
            echo " $f"
            long_lines=true
        fi
    done
    $long_lines
}

check_relnotes() {
    if git diff --exit-code "$REVRANGE" master/docs/relnotes/index.rst >/dev/null 2>&1; then
        return 1
    else
        return 0
    fi
}

run_tests() {
    if [ -n "${TRIALTMP}" ]; then
        TEMP_DIRECTORY_OPT="--temp-directory ${TRIALTMP}"
    fi
    sandbox/bin/trial --reporter summary ${TEMP_DIRECTORY_OPT} ${TEST}
}

if ! git diff --no-ext-diff --quiet --exit-code; then
    not_ok "changed files in working copy"
    exit 1
fi

echo "${MAGENTA}Validating the following commits:${NORM}"
git log "$REVRANGE" --pretty=oneline || exit 1

status "running tests"
run_tests || not_ok "tests failed"

status "checking formatting"
check_tabs && not_ok "$REVRANGE adds tabs"
check_long_lines && not_ok "$REVRANGE adds long lines"

status "checking for release notes"
check_relnotes || not_ok "$REVRANGE does not add release notes"

status "running pyflakes"
sandbox/bin/pyflakes master/buildbot slave/buildslave || not_ok "failed pyflakes"

status "building docs"
make -C master/docs VERSION=latest clean html || not_ok "docs failed"

echo ""
if $ok; then
    echo "${GREEN}GOOD!${NORM}"
    exit 0
else
    echo "${RED}NO GOOD!${NORM}$problem_summary"
    exit 1
fi
