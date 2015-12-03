#! /bin/bash
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

## parse options

quick=false
no_js=false
help=false
while [ $# -gt 0 ]; do
    case $1 in
        --quick) quick=true ;;
        --no-js) no_js=true ;;
        --help) help=true ;;
        -*) echo "$0: error - unrecognized option $1" 1>&2; help=true ;;
        *) REVRANGE="$1..HEAD" ;;
    esac
    shift
done

if $help; then
    echo "USAGE: common/validate.sh [oldrev] [--quick] [--no-js] [--help]"
    echo "  This script will test a set of patches (oldrev..HEAD) for basic acceptability as a patch"
    echo "  Run it in an activated virtualenv with the current Buildbot installed, as well as"
    echo "      sphinx, pyflakes, mock, and so on"
    echo "To use a different directory for tests, pass TRIALTMP=/path as an env variable"
    echo "if --quick is passed validate will skip unit tests and concentrate on coding style"
    echo "if --no-js is passed validate will skip tests that require Node and NPM"
    echo "if --help is passed validate will output this message and exit"
    echo "if no oldrev is passed validate will assume master...HEAD"
    exit 1
fi

[ -z "$REVRANGE" ] && REVRANGE="master..HEAD"

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
    else
        warning "please provide a TRIALTMP env variable pointing to a ramfs for 30x speed up of the integration tests"
    fi
    find . -name \*.pyc -exec rm {} \;
    trial --reporter text ${TEMP_DIRECTORY_OPT} ${TEST}
}

if ! git diff --no-ext-diff --quiet --exit-code; then
    not_ok "changed files in working copy"
    if ! $quick; then
        exit 1
    fi
fi

# get a list of changed files, used below; this uses a tempfile to work around
# shell behavior when piping to 'while'
tempfile=$(mktemp -t tmp.XXXXXX)
trap "rm -f ${tempfile}; exit 1" 1 2 3 15
git diff --name-only $REVRANGE | grep '\.py$' | grep -v '\(^master/docs\|/setup\.py\)' > ${tempfile}
py_files=()
while read line; do
    if test -f "${line}"; then
        py_files+=($line)
    fi
done < ${tempfile}

echo "${MAGENTA}Validating the following commits:${NORM}"
git log "$REVRANGE" --pretty=oneline || exit 1

if ! $quick && ! $no_js; then
    for module in www/base www/console_view www/waterfall_view www/codeparameter;
    do
        status "running 'setup.py develop' for $module"
        if ! (cd $module; python setup.py develop >/dev/null ); then
            warning "$module/setup.py failed; retrying with cleared libs/"
            rm -rf "$module/libs"
            (cd $module; python setup.py develop >/dev/null ) || not_ok "$module/setup.py failed"
        fi
    done
else
    warning "Skipping JavaScript Tests"
fi

if ! $quick; then
    status "running Python tests"
    run_tests || not_ok "Python tests failed"
elif [ -z `which cctrial` ]; then
    warning "Skipping Python Tests ('pip install cctrial' for quick tests)"
else
    cctrial -H buildbot buildslave || not_ok "Python tests failed"
fi

status "checking formatting"
check_tabs && not_ok "$REVRANGE adds tabs"
check_long_lines && warning "$REVRANGE adds long lines"
check_yield_defer_returnValue && not_ok "$REVRANGE yields defer.returnValue"

status "checking for release notes"
check_relnotes || warning "$REVRANGE does not add release notes"

status "checking import module convention in modified files"
RES=true
for filename in ${py_files[@]}; do
  if ! python common/fiximports.py "$filename"; then
    echo "cannot fix imports of $filename"
    RES=false
  fi
done
$RES || warning "some import fixes failed -- not enforcing for now"

status "running autopep8"
if [[ -z `which autopep8` ]]; then
    warning "autopep8 is not installed"
elif [[ ! -f common/pep8rc ]]; then
    warning "common/pep8rc not found"
else
    changes_made=false
    for filename in ${py_files[@]}; do
        LINEWIDTH=$(grep -E "max-line-length" common/pep8rc | sed 's/ //g' | cut -d'=' -f 2)
        # even if we dont enforce errors, if they can be fixed automatically, thats better..
        IGNORES=E123,E501,W6
        # ignore is not None for SQLAlchemy code..
        if [[ "$filename" =~ "/db/" ]]; then
            IGNORES=$IGNORES,E711,E712
        fi
        autopep8 --in-place --max-line-length=$LINEWIDTH --ignore=$IGNORES "$filename"
        if ! git diff --quiet --exit-code "$filename"; then
            changes_made=true
        fi
    done
    if ${changes_made}; then
        not_ok "autopep8 made changes"
    fi
fi

status "running pep8"
if [[ -z `which pep8` ]]; then
    warning "pep8 is not installed"
elif [[ ! -f common/pep8rc ]]; then
    warning "common/pep8rc not found"
else
    pep8_ok=true
    for filename in ${py_files[@]}; do
        if ! pep8 --config=common/pep8rc "$filename"; then
            pep8_ok=false
        fi
    done
    $pep8_ok || not_ok "pep8 failed"
fi

status "running pyflakes"
if [[ -z `which pyflakes` ]]; then
    warning "pyflakes is not installed"
else
    pyflakes_ok=true
    for filename in ${py_files[@]}; do
        if ! pyflakes "$filename"; then
            pyflakes_ok=false
        fi
    done
    $pyflakes_ok || not_ok "pyflakes failed"
fi


status "running pylint"
if [[ -z `which pylint` ]]; then
    warning "pylint is not installed"
elif [[ ! -f common/pylintrc ]]; then
    warning "common/pylintrc not found"
else
    pylint_ok=true
    for filename in ${py_files[@]}; do
        if ! pylint --rcfile=common/pylintrc --disable=R,line-too-long --enable=W0611 --output-format=text --report=no "$filename"; then
            pylint_ok=false
        fi
    done
    $pylint_ok || not_ok "pylint failed"
fi

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
