#! /bin/bash
REVRANGE="$1..HEAD"
TEST='buildbot.test buildslave.test'

# some colors
# plain
_ESC=$'\e'
GREEN="$_ESC[0;32m"
MAGENTA="$_ESC[0;35m"
RED="$_ESC[0;31m"
LTCYAN="$_ESC[1;36m"
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
    echo "${LTCYAN}-- ${*} --${NORM}"
}

ok=true
problem_summary=""
not_ok() {
    ok=false
    echo "${RED}** ${*} **${NORM}"
    problem_summary="$problem_summary"$'\n'"${RED}**${NORM} ${*}"
}

warning() {
    echo "${YELLOW}** ${*} **${NORM}"
    problem_summary="$problem_summary"$'\n'"${YELLOW}**${NORM} ${*} (warning)"
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


check_yield_defer_returnValue() {
    local yields=false
    if git diff "$REVRANGE" | grep '+.*yield defer.returnValue'; then
        yields=true
    fi
    $yields
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
    find . -name \*.pyc -exec rm {} \;
    trial --reporter text ${TEMP_DIRECTORY_OPT} ${TEST}
}

if ! git diff --no-ext-diff --quiet --exit-code; then
    not_ok "changed files in working copy"
    exit 1
fi

echo "${MAGENTA}Validating the following commits:${NORM}"
git log "$REVRANGE" --pretty=oneline || exit 1

status "running 'setup.py develop' for www"
(cd www; python setup.py develop 2>&1 >/dev/null) || not_ok "www/setup.py failed"

status "running tests"
run_tests || not_ok "tests failed"

status "checking formatting"
check_tabs && not_ok "$REVRANGE adds tabs"
check_long_lines && warning "$REVRANGE adds long lines"
check_yield_defer_returnValue && not_ok "$REVRANGE yields defer.returnValue"

status "checking for release notes"
check_relnotes || warning "$REVRANGE does not add release notes"

status "running pyflakes"
pyflakes master/buildbot slave/buildslave || not_ok "failed pyflakes"

status "check and fix style issues"
git diff --name-only $REVRANGE | common/style_check_and_fix.sh || not_ok "style issues"

[[ `git diff --name-only HEAD | wc -l` -gt 0 ]] && not_ok "style fixes to be committed"

if git diff --name-only $REVRANGE | grep docs ; then
    status "building docs"
    make -C master/docs VERSION=latest clean html || not_ok "docs failed"
else
    status "not building docs, because it was not changed"
fi

echo ""
if $ok; then
    echo "${GREEN}GOOD!${NORM}"
    exit 0
else
    echo "${RED}NO GOOD!${NORM}$problem_summary"
    exit 1
fi
