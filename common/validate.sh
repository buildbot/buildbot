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

# get a list of changed files, used below; this uses a tempfile to work around
# shell behavior when piping to 'while'
tempfile=$(mktemp)
trap 'rm -f ${tempfile}' 1 2 3 15
git diff --name-only $REVRANGE | grep '\.py$' | grep -v '\(^master/\(contrib\|docs\)\|/setup\.py\)' > ${tempfile}
py_files=()
while read line; do
    py_files+=($line)
done < ${tempfile}

echo "${MAGENTA}Validating the following commits:${NORM}"
git log "$REVRANGE" --pretty=oneline || exit 1

status "running tests"
run_tests || not_ok "tests failed"

status "checking formatting"
check_tabs && not_ok "$REVRANGE adds tabs"

status "checking for release notes"
check_relnotes || warning "$REVRANGE does not add release notes"

status "running pyflakes"
pyflakes master/buildbot slave/buildslave || not_ok "failed pyflakes"

status "checking import module convention in modified files"
RES=true
for filename in ${py_files[@]}; do
  if ! python common/fiximports.py "$filename"; then
    echo "cannot fix imports of $filename"
    RES=false
  fi
done
$RES || warning "some import fixes failed -- not enforcing for now"

statis "running autopep8"
if [[ -z `which autopep8` ]]; then
    warning "autopep8 is not installed"
else
    for filename in ${py_files[@]}; do
      if [[ -f common/pep8rc ]]; then
        LINEWIDTH=$(grep -E "max-line-length" common/pep8rc | sed 's/ //g' | cut -d'=' -f 2)
        # even if we dont enforce errors, if they can be fixed automatically, thats better..
        IGNORES=E501,W6
        # ignore is not None for SQLAlchemy code..
        if [[ "$filename" =~ "/db/" ]]; then
          IGNORES=$IGNORES,E711,E712
        fi
        autopep8 --in-place --max-line-length=$LINEWIDTH --ignore=$IGNORES "$filename"
      else
        warning "common/pep8rc not found"
      fi
    done
fi

[[ `git diff --name-only HEAD | wc -l` -gt 0 ]] && not_ok "style fixes to be committed"

if git diff --name-only $REVRANGE | grep ^master/docs/ ; then
    status "building docs"
    make -C master/docs VERSION=latest clean html || not_ok "docs failed"
else
    status "not building docs, because it was not changed"
fi

echo ""
if $ok; then
    if [ -z "${problem_summary}" ]; then
        echo "${GREEN}GOOD!${NORM}"
    else
        echo "${YELLOW}WARNINGS${NORM}${problem_summary}"
    fi
    exit 0
else
    echo "${RED}NO GOOD!${NORM}${problem_summary}"
    exit 1
fi
