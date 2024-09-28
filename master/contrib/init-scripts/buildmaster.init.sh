#!/bin/bash

### Maintain compatibility with chkconfig
# chkconfig: 2345 83 17
# description: buildmaster

### BEGIN INIT INFO
# Provides:          buildmaster
# Required-Start:    $remote_fs
# Required-Stop:     $remote_fs
# Default-Start:     2 3 4 5
# Default-Stop:      0 1 6
# Short-Description: Buildbot master init script
# Description:       This file allows running buildbot master instances at
#                    startup
### END INIT INFO

PATH=/sbin:/bin:/usr/sbin:/usr/bin
MASTER_RUNNER=/usr/bin/buildbot

. /lib/lsb/init-functions

# Source buildmaster configuration
[[ -r /etc/default/buildmaster ]] && . /etc/default/buildmaster
#[[ -r /etc/sysconfig/buildmaster ]] && . /etc/sysconfig/buildmaster

# Or define/override the configuration here
#MASTER_ENABLED[1]=0                    # 1-enabled, 0-disabled
#MASTER_NAME[1]="buildmaster #1"        # short name printed on start/stop
#MASTER_USER[1]="buildbot"              # user to run master as
#MASTER_BASEDIR[1]=""                   # basedir to master (absolute path)
#MASTER_OPTIONS[1]=""                   # buildbot options
#MASTER_PREFIXCMD[1]=""                 # prefix command, i.e. nice, linux32, dchroot

if [[ ! -x ${MASTER_RUNNER} ]]; then
    log_failure_msg "does not exist or not an executable file: ${MASTER_RUNNER}"
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


function master_config_valid() {
    # Function validates buildmaster instance startup variables based on array
    # index
    local errors=0
    local index=$1

    if ! is_enabled "${MASTER_ENABLED[$index]}" && ! is_disabled "${MASTER_ENABLED[$index]}" ; then
        log_warning_msg "buildmaster #${i}: invalid enabled status"
        errors=$(($errors+1))
    fi

    if [[ -z ${MASTER_NAME[$index]} ]]; then
        log_failure_msg "buildmaster #${i}: no name"
        errors=$(($errors+1))
    fi

    if [[ -z ${MASTER_USER[$index]} ]]; then
        log_failure_msg "buildmaster #${i}: no run user specified"
        errors=$( ($errors+1) )
    elif ! getent passwd ${MASTER_USER[$index]} >/dev/null; then
        log_failure_msg "buildmaster #${i}: unknown user ${MASTER_USER[$index]}"
        errors=$(($errors+1))
    fi

    if [[ ! -d "${MASTER_BASEDIR[$index]}" ]]; then
        log_failure_msg "buildmaster ${i}: basedir does not exist ${MASTER_BASEDIR[$index]}"
        errors=$(($errors+1))
    fi

    return $errors
}

function check_config() {
    itemcount="${#MASTER_ENABLED[@]}
               ${#MASTER_NAME[@]}
               ${#MASTER_USER[@]}
               ${#MASTER_BASEDIR[@]}
               ${#MASTER_OPTIONS[@]}
               ${#MASTER_PREFIXCMD[@]}"

    if [[ $(echo "$itemcount" | tr -d ' ' | sort -u | wc -l) -ne 1 ]]; then
        log_failure_msg "MASTER_* arrays must have an equal number of elements!"
        return 1
    fi

    errors=0
    for i in $( seq ${#MASTER_ENABLED[@]} ); do
        if is_disabled "${MASTER_ENABLED[$i]}" ; then
            log_warning_msg "buildmaster #${i}: disabled"
            continue
        fi
        master_config_valid $i
        errors=$(($errors+$?))
    done

    [[ $errors == 0 ]]; return $?
}

check_config || exit $?

function iscallable () { type $1 2>/dev/null | grep -q 'shell function'; }

function master_op () {
    op=$1 ; mi=$2

    ${MASTER_PREFIXCMD[$mi]} \
    su -s /bin/sh \
    -c "$MASTER_RUNNER $op ${MASTER_OPTIONS[$mi]} ${MASTER_BASEDIR[$mi]} > /dev/null" \
    - ${MASTER_USER[$mi]}
    return $?
}

function do_op () {
    errors=0
    for i in $( seq ${#MASTER_ENABLED[@]} ); do
        if [ -n "$4" ] && [ "$4" != "${MASTER_NAME[$i]}" ] ; then
            continue
        elif is_disabled "${MASTER_ENABLED[$i]}" && [ -z "$4" ] ; then
            continue
        fi

        # Some rhels don't come with all the lsb goodies
        if iscallable log_daemon_msg; then
            log_daemon_msg "$3 \"${MASTER_NAME[$i]}\""
            if eval $1 $2 $i; then
                log_end_msg 0
            else
                log_end_msg 1
                errors=$(($errors+1))
            fi
        else
            if eval $1 $2 $i; then
                log_success_msg "$3 \"${MASTER_NAME[$i]}\""
            else
                log_failure_msg "$3 \"${MASTER_NAME[$i]}\""
                errors=$(($errors+1))
            fi
        fi
    done
    return $errors
}

case "$1" in
    start)
        do_op "master_op" "start" "Starting buildmaster" "$2"
        exit $?
        ;;
    stop)
        do_op "master_op" "stop" "Stopping buildmaster" "$2"
        exit $?
        ;;
    reload)
        do_op "master_op" "reconfig" "Reloading buildmaster" "$2"
        exit $?
        ;;
    restart|force-reload)
        do_op "master_op" "restart" "Restarting buildmaster" "$2"
        exit $?
        ;;
    upgrade)
        do_op "master_op" "upgrade-master" "Upgrading buildmaster" "$2"
        exit $?
        ;;
    *)
        echo "Usage: $0 {start|stop|restart|reload|force-reload|upgrade}"
        exit 1
        ;;
esac

exit 0
