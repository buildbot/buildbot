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
### END INIT INFO

PATH=/sbin:/bin:/usr/sbin:/usr/bin
MASTER_RUNNER=/usr/bin/buildbot

. /lib/lsb/init-functions

# Source buildmaster configuration
[[ -r /etc/default/buildmaster ]] && . /etc/default/buildmaster
#[[ -r /etc/sysconfig/buildmaster ]] && . /etc/sysconfig/buildmaster

# Or define/override the configuration here
#MASTER_ENABLED[1]=0                    # 0-enabled, other-disabled
#MASTER_NAME[1]="buildmaster #1"        # short name printed on start/stop
#MASTER_USER[1]="buildbot"              # user to run master as
#MASTER_BASEDIR[1]=""                   # basedir to master (absolute path)
#MASTER_OPTIONS[1]=""                   # buildbot options  
#MASTER_PREFIXCMD[1]=""                 # prefix command, i.e. nice, linux32, dchroot

if [[ ! -x ${MASTER_RUNNER} ]]; then
    log_failure_msg "does not exist or not an executable file: ${MASTER_RUNNER}"
    exit 1
fi

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
        if [[ "${MASTER_ENABLED[$i]}" != "0" ]]; then
            log_warning_msg "buildmaster #${i}: disabled"
            continue
        fi

        if [[ -z ${MASTER_NAME[$i]} ]]; then
            log_failure_msg "buildmaster #${i}: no name"
            errors=$(($errors+1))
        fi

        if [[ -z ${MASTER_USER[$i]} ]]; then
            log_failure_msg "buildmaster #${i}: no run user specified"
            errors=$( ($errors+1) )
        elif ! getent passwd ${MASTER_USER[$i]} >/dev/null; then
            log_failure_msg "buildmaster #${i}: unknown user ${MASTER_USER[$i]}"
            errors=$(($errors+1))
        fi

        if [[ ! -d "${MASTER_BASEDIR[$i]}" ]]; then
            log_failure_msg "buildmaster ${i}: basedir does not exist ${MASTER_BASEDIR[$i]}"
            errors=$(($errors+1))
        fi
    done

    [[ $errors == 0 ]]; return $?
}

check_config || exit $?

function iscallable () { type $1 2>/dev/null | grep -q 'shell function'; }

function master_op () {
    op=$1 ; mi=$2

    ${MASTER_PREFIXCMD[$1]} \
    su -s /bin/sh \
    -c "$MASTER_RUNNER $op --quiet ${MASTER_OPTIONS[$mi]} ${MASTER_BASEDIR[$mi]}" \
    - ${MASTER_USER[$mi]}
    return $?
}

function do_op () {
    errors=0
    for i in $( seq ${#MASTER_ENABLED[@]} ); do
        [[ "${MASTER_ENABLED[$i]}" != "0" ]] && continue

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
        do_op "master_op" "start" "Starting buildmaster"
        exit $?
        ;;
    stop)
        do_op "master_op" "stop" "Stopping buildmaster"
        exit $?
        ;;
    reload)
        do_op "master_op" "reconfig" "Reloading buildmaster"
        exit $?
        ;;
    restart|force-reload)
        do_op "master_op" "restart" "Restarting buildmaster"
        exit $?
        ;;
    *)
        echo "Usage: $0 {start|stop|restart|reload|force-reload}"
        exit 1
        ;;
esac

exit 0
