#!/bin/bash

### Maintain compatibility with chkconfig
# chkconfig: 2345 83 17
# description: buildbot-worker

### BEGIN INIT INFO
# Provides:          buildbot-worker
# Required-Start:    $remote_fs
# Required-Stop:     $remote_fs
# Default-Start:     2 3 4 5
# Default-Stop:      0 1 6
# Short-Description: Buildbot worker init script
# Description:       This file allows running buildbot worker instances at
#                    startup
### END INIT INFO

PATH=/sbin:/bin:/usr/sbin:/usr/bin
WORKER_RUNNER=/usr/bin/buildbot-worker


# Source buildbot-worker configuration
[[ -r /etc/default/buildbot-worker ]] && . /etc/default/buildbot-worker
#[[ -r /etc/sysconfig/buildbot-worker ]] && . /etc/sysconfig/buildbot-worker

# Or define/override the configuration here
#WORKER_ENABLED[1]=0                    # 0-enabled, other-disabled
#WORKER_NAME[1]="buildbot-worker #1"    # short name printed on start/stop
#WORKER_USER[1]="buildbot"              # user to run worker as
#WORKER_BASEDIR[1]=""                   # basedir to worker (absolute path)
#WORKER_OPTIONS[1]=""                   # buildbot options
#WORKER_PREFIXCMD[1]=""                 # prefix command, i.e. nice, linux32, dchroot


# Get some LSB-like functions
if [ -r /lib/lsb/init-functions ]; then
    . /lib/lsb/init-functions
else
    function log_success_msg() {
        echo "$@"
    }
    function log_failure_msg() {
        echo "$@"
    }
    function log_warning_msg() {
        echo "$@"
    }
fi


# Some systems don't have seq (e.g. Solaris)
if type seq >/dev/null 2>&1; then
    :
else
    function seq() {
        for ((i=1; i<=$1; i+=1)); do
            echo $i
        done
    }
fi


if [[ ! -x ${WORKER_RUNNER} ]]; then
    log_failure_msg "does not exist or not an executable file: ${WORKER_RUNNER}"
    exit 1
fi

function is_enabled() {
    ANSWER=`echo $1|tr "[:upper:]" "[:lower:]"`
    [[ "$ANSWER" == "yes" ]] || [[ "$ANSWER" == "true" ]] || [[ "$ANSWER" ==  "1" ]]
    return $?
}

function is_disabled() {
    ANSWER=`echo $1|tr "[:upper:]" "[:lower:]"`
    [[ "$ANSWER" == "no" ]] || [[ "$ANSWER" == "false" ]] || [[ "$ANSWER" ==  "0" ]]
    return $?
}


function worker_config_valid() {
    # Function validates buildbot worker instance startup variables based on 
    # array index
    local errors=0
    local index=$1

    if ! is_enabled "${WORKER_ENABLED[$index]}" && ! is_disabled "${WORKER_ENABLED[$index]}" ; then
        log_warning_msg "buildbot-worker #${index}: invalid enabled status"
        errors=$(($errors+1))
    fi

    if [[ -z ${WORKER_NAME[$index]} ]]; then
        log_failure_msg "buildbot-worker #${index}: no name"
        errors=$(($errors+1))
    fi

    if [[ -z ${WORKER_USER[$index]} ]]; then
        log_failure_msg "buildbot-worker #${index}: no run user specified"
        errors=$( ($errors+1) )
    elif ! getent passwd ${WORKER_USER[$index]} >/dev/null; then
        log_failure_msg "buildbot-worker #${index}: unknown user ${WORKER_USER[$index]}"
        errors=$(($errors+1))
    fi

    if [[ ! -d "${WORKER_BASEDIR[$index]}" ]]; then
        log_failure_msg "buildbot-worker ${index}: basedir does not exist ${WORKER_BASEDIR[$index]}"
        errors=$(($errors+1))
    fi

    return $errors
}

function check_config() {
    itemcount="${#WORKER_ENABLED[@]}
               ${#WORKER_NAME[@]}
               ${#WORKER_USER[@]}
               ${#WORKER_BASEDIR[@]}
               ${#WORKER_OPTIONS[@]}
               ${#WORKER_PREFIXCMD[@]}"

    if [[ $(echo "$itemcount" | tr -d ' ' | sort -u | wc -l) -ne 1 ]]; then
        log_failure_msg "WORKER_* arrays must have an equal number of elements!"
        return 1
    fi

    errors=0
    for i in $( seq ${#WORKER_ENABLED[@]} ); do
        if is_disabled "${WORKER_ENABLED[$i]}" ; then
            log_warning_msg "buildbot-worker #${i}: disabled"
            continue
        fi
        worker_config_valid $i
        errors=$(($errors+$?))
    done

    [[ $errors == 0 ]]; return $?
}

check_config || exit $?

function iscallable () { type $1 2>/dev/null | grep -q 'shell function'; }

function worker_op () {
    op=$1 ; mi=$2

    if [ `uname` = SunOS ]; then
        suopt=""
    else
        suopt="-s /bin/sh"
    fi
    ${WORKER_PREFIXCMD[$mi]} \
    su $suopt - ${WORKER_USER[$mi]} \
    -c "$WORKER_RUNNER $op ${WORKER_OPTIONS[$mi]} ${WORKER_BASEDIR[$mi]} > /dev/null"
    return $?
}

function do_op () {
    errors=0
    for i in $( seq ${#WORKER_ENABLED[@]} ); do
        if [ -n "$4" ] && [ "$4" != "${WORKER_NAME[$i]}" ] ; then
            continue
        elif is_disabled "${WORKER_ENABLED[$i]}" && [ -z "$4" ] ; then
            continue
        fi

        # Some rhels don't come with all the lsb goodies
        if iscallable log_daemon_msg; then
	        log_daemon_msg "$3 \"${WORKER_NAME[$i]}\""
            if eval $1 $2 $i; then
                log_end_msg 0
            else
                log_end_msg 1
                errors=$(($errors+1))
            fi
        else
            if eval $1 $2 $i; then
                log_success_msg "$3 \"${WORKER_NAME[$i]}\""
            else
                log_failure_msg "$3 \"${WORKER_NAME[$i]}\""
                errors=$(($errors+1))
            fi
        fi
    done
    return $errors
}

case "$1" in
    start)
        do_op "worker_op" "start" "Starting buildbot-worker" "$2"
        exit $?
        ;;
    stop)
        do_op "worker_op" "stop" "Stopping buildbot-worker" "$2"
        exit $?
        ;;
    reload)
        do_op "worker_op" "reload" "Reloading buildbot-worker" "$2"
        exit $?
        ;;
    restart|force-reload)
        do_op "worker_op" "restart" "Restarting buildbot-worker" "$2"
        exit $?
        ;;
    *)
        echo "Usage: $0 {start|stop|restart|reload|force-reload}"
        exit 1
        ;;
esac

exit 0
