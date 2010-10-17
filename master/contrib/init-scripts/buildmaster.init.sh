#!/bin/bash

### BEGIN INIT INFO
# Provides:          buildmaster
# Required-Start:    $remote_fs
# Required-Stop:     $remote_fs buildslave
# Default-Start:     2 3 4 5
# Default-Stop:      0 1 6
### END INIT INFO

PATH=/sbin:/bin:/usr/sbin:/usr/bin
MASTER_RUNNER=/usr/bin/buildbot

# Source buildmaster configuration
[[ -r /etc/default/buildbot ]] && . /etc/default/buildbot

test -x ${MASTER_RUNNER} || exit 0

. /lib/lsb/init-functions

function check_config() {
    itemcount="${#MASTER_ENABLED[@]}
               ${#MASTER_NAME[@]}
               ${#MASTER_USER[@]}
               ${#MASTER_BASEDIR[@]}
               ${#MASTER_OPTIONS[@]}
               ${#MASTER_PREFIXCMD[@]}" 

    if [[ $(echo "$itemcount" | tr -d ' ' | sort -u | wc -l) -ne 1 ]]; then
        echo "@todo: think of error msg" >&2
        return 1
    fi

    errors=0
    for i in $( seq ${#MASTER_ENABLED[@]} ); do
        if [[ ${MASTER_ENABLED[$i]} -ne 0 ]]; then 
            echo "buildmaster #${i}: unknown run status" >&2
            errors=$(($errors+1))
        fi

        if [[ -z ${MASTER_NAME[$i]} ]]; then
            echo "buildmaster #${i}: no name" >&2
            errors=$(($errors+1))
        fi

        if [[ -z ${MASTER_USER[$i]} ]]; then
            echo "buildmaster #${i}: no run user specified" >&2
            errors=$( ($errors+1) )
        elif ! getent passwd ${MASTER_USER[$i]} >/dev/null; then
            echo "buildmaster #${i}: unknown user ${MASTER_USER[$i]}" >&2
            errors=$(($errors+1))
        fi

        if [[ ! -d "${MASTER_BASEDIR[$i]}" ]]; then
            echo "buildmaster ${i}: basedir does not exist ${MASTER_BASEDIR[$i]}" >&2
            errors=$(($errors+1))
        fi
    done

    [[ $errors == 0 ]]; return $?
}

check_config || exit $?

function master_op () {
    op=$1

    ${MASTER_PREFIXCMD[$1]} \
    su -s /bin/sh \
    -c "$MASTER_RUNNER $op --quiet ${MASTER_OPTIONS[$1]} ${MASTER_BASEDIR[$1]}" \
    - ${MASTER_USER[$1]}
    return $?
}

function do_op () {
    errors=0
    for i in $( seq ${#MASTER_ENABLED[@]} ); do
        [[ ${MASTER_ENABLED[$i]} -ne 0 ]] && continue

	    log_daemon_msg "$2 \"${MASTER_NAME[$i]}\""
        if $(eval $1 $i); then
            log_end_msg 0
        else
            log_end_msg 1
            errors=$(($errors+1))
        fi
    done
    return $errors
}

case "$1" in
    start)
        do_op "master_op start" "Starting buildmaster"
        exit $?
        ;;
    stop)
        do_op "master_op stop" "Stopping buildmaster"
        exit $?
        ;;
    reload)
        do_op "master_op reload" "Reloading buildmaster"
        exit $?
        ;;
    restart|force-reload)
        do_op "master_op restart" "Restarting buildmaster"
        exit $?
        ;;
    *)
        log_warning_msg "Usage: $0 {start|stop|restart|reload|force-reload}"
        exit 1
        ;;
esac

exit 0
