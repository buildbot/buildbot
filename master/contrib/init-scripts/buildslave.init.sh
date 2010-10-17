#!/bin/bash

### BEGIN INIT INFO
# Provides:          buildslave
# Required-Start:    $remote_fs
# Required-Stop:     $remote_fs
# Default-Start:     2 3 4 5
# Default-Stop:      0 1 6
### END INIT INFO

PATH=/sbin:/bin:/usr/sbin:/usr/bin
BUILDSLAVE_RUNNER=/usr/bin/buildslave

# Source buildslave configuration
[[ -r /etc/default/buildslave ]] && . /etc/default/buildslave

test -x ${SLAVE_RUNNER} || exit 0

. /lib/lsb/init-functions

function check_config() {
    itemcount="${#SLAVE_ENABLED[@]}
               ${#SLAVE_NAME[@]}
               ${#SLAVE_USER[@]}
               ${#SLAVE_BASEDIR[@]}
               ${#SLAVE_OPTIONS[@]}
               ${#SLAVE_PREFIXCMD[@]}" 

    if [[ $(echo "$itemcount" | tr -d ' ' | sort -u | wc -l) -ne 1 ]]; then
        echo "@todo: think of error msg" >&2
        return 1
    fi

    errors=0
    for i in $( seq ${#SLAVE_ENABLED[@]} ); do
        if [[ ${SLAVE_ENABLED[$i]} -ne 0 ]]; then 
            echo "buildslave #${i}: unknown run status" >&2
            errors=$(($errors+1))
        fi

        if [[ -z ${SLAVE_NAME[$i]} ]]; then
            echo "buildslave #${i}: no name" >&2
            errors=$(($errors+1))
        fi

        if [[ -z ${SLAVE_USER[$i]} ]]; then
            echo "buildslave #${i}: no run user specified" >&2
            errors=$( ($errors+1) )
        elif ! getent passwd ${SLAVE_USER[$i]} >/dev/null; then
            echo "buildslave #${i}: unknown user ${SLAVE_USER[$i]}" >&2
            errors=$(($errors+1))
        fi

        if [[ ! -d "${SLAVE_BASEDIR[$i]}" ]]; then
            echo "buildslave ${i}: basedir does not exist ${SLAVE_BASEDIR[$i]}" >&2
            errors=$(($errors+1))
        fi
    done

    [[ $errors == 0 ]]; return $?
}

check_config || exit $?

function slave_op () {
    op=$1

    ${SLAVE_PREFIXCMD[$1]} \
    su -s /bin/sh \
    -c "$BUILDSLAVE_RUNNER $op --quiet ${MASTER_OPTIONS[$1]} ${MASTER_BASEDIR[$1]}" \
    - ${SLAVE_USER[$1]}
    return $?
}

function do_op () {
    errors=0
    for i in $( seq ${#SLAVE_ENABLED[@]} ); do
        [[ ${SLAVE_ENABLED[$i]} -ne 0 ]] && continue

	    log_daemon_msg "$3 \"${SLAVE_NAME[$i]}\""
        if $(eval $1 $2 $i); then
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
        do_op "slave_op" "start" "Starting buildslave"
        exit $?
        ;;
    stop)
        do_op "slave_op" "stop" "Stopping buildslave"
        exit $?
        ;;
    reload)
        do_op "slave_op" "reload" "Reloading buildslave"
        exit $?
        ;;
    restart|force-reload)
        do_op "slave_op" "restart" "Restarting buildslave"
        exit $?
        ;;
    *)
        log_warning_msg "Usage: $0 {start|stop|restart|reload|force-reload}"
        exit 1
        ;;
esac

exit 0
