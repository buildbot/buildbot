#!/bin/bash

### BEGIN INIT INFO
# Provides:          buildslave
# Required-Start:    $remote_fs
# Required-Stop:     $remote_fs
# Default-Start:     2 3 4 5
# Default-Stop:      0 1 6
### END INIT INFO

PATH=/sbin:/bin:/usr/sbin:/usr/bin
SLAVE_RUNNER=/usr/bin/buildslave

. /lib/lsb/init-functions

# Source buildslave configuration 
[[ -r /etc/default/buildslave ]] && . /etc/default/buildslave
#[[ -r /etc/sysconfig/buildslave ]] && . /etc/sysconfig/buildslave

# Or define/override the configuration here
#SLAVE_ENABLED[1]=0                    # 0-enabled, other-disabled
#SLAVE_NAME[1]="buildslave #1"         # short name printed on start/stop
#SLAVE_USER[1]="buildbot"              # user to run slave as
#SLAVE_BASEDIR[1]=""                   # basedir to slave (absolute path)
#SLAVE_OPTIONS[1]=""                   # buildbot options  
#SLAVE_PREFIXCMD[1]=""                 # prefix command, i.e. nice, linux32, dchroot

if [[ ! -x ${SLAVE_RUNNER} ]]; then
    log_failure_msg "does not exist or not an executable file: ${SLAVE_RUNNER}"
    exit 1
fi

function check_config() {
    itemcount="${#SLAVE_ENABLED[@]}
               ${#SLAVE_NAME[@]}
               ${#SLAVE_USER[@]}
               ${#SLAVE_BASEDIR[@]}
               ${#SLAVE_OPTIONS[@]}
               ${#SLAVE_PREFIXCMD[@]}" 

    if [[ $(echo "$itemcount" | tr -d ' ' | sort -u | wc -l) -ne 1 ]]; then
        log_failure_msg "SLAVE_* arrays must have an equal number of elements!"
        return 1
    fi

    errors=0
    for i in $( seq ${#SLAVE_ENABLED[@]} ); do
        if [[ ${SLAVE_ENABLED[$i]} -ne 0 ]]; then 
            log_failure_msg "buildslave #${i}: unknown run status"
            errors=$(($errors+1))
        fi

        if [[ -z ${SLAVE_NAME[$i]} ]]; then
            log_failure_msg "buildslave #${i}: no name"
            errors=$(($errors+1))
        fi

        if [[ -z ${SLAVE_USER[$i]} ]]; then
            log_failure_msg "buildslave #${i}: no run user specified"
            errors=$( ($errors+1) )
        elif ! getent passwd ${SLAVE_USER[$i]} >/dev/null; then
            log_failure_msg "buildslave #${i}: unknown user ${SLAVE_USER[$i]}"
            errors=$(($errors+1))
        fi

        if [[ ! -d "${SLAVE_BASEDIR[$i]}" ]]; then
            log_failure_msg "buildslave ${i}: basedir does not exist ${SLAVE_BASEDIR[$i]}"
            errors=$(($errors+1))
        fi
    done

    [[ $errors == 0 ]]; return $?
}

check_config || exit $?

function iscallable () { type $1 2>/dev/null | grep -q 'shell function'; }

function slave_op () {
    op=$1 ; mi=$2

    ${SLAVE_PREFIXCMD[$1]} \
    su -s /bin/sh \
    -c "$SLAVE_RUNNER $op --quiet ${SLAVE_OPTIONS[$mi]} ${SLAVE_BASEDIR[$mi]}" \
    - ${SLAVE_USER[$mi]}
    return $?
}

function do_op () {
    errors=0
    for i in $( seq ${#SLAVE_ENABLED[@]} ); do
        [[ ${SLAVE_ENABLED[$i]} -ne 0 ]] && continue

        # Some rhels don't come with all the lsb goodies
        if iscallable log_daemon_msg; then
	        log_daemon_msg "$3 \"${SLAVE_NAME[$i]}\""
            if eval $1 $2 $i; then
                log_end_msg 0
            else
                log_end_msg 1
                errors=$(($errors+1))
            fi
        else
            if eval $1 $2 $i; then
                log_success_msg "$3 \"${SLAVE_NAME[$i]}\""
            else
                log_failure_msg "$3 \"${SLAVE_NAME[$i]}\""
                errors=$(($errors+1))
            fi
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
        echo "Usage: $0 {start|stop|restart|reload|force-reload}"
        exit 1
        ;;
esac

exit 0
