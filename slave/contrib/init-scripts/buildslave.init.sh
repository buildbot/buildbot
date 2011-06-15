#!/bin/bash

### Maintain compatibility with chkconfig
# chkconfig: 2345 83 17
# description: buildslave

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


function slave_config_valid() {
    # Function validates buildmaster instance startup variables based on array
    # index
    local errors=0
    local index=$1

    if ! is_enabled "${SLAVE_ENABLED[$index]}" && ! is_disabled "${SLAVE_ENABLED[$index]}" ; then
        log_warning_msg "buildmaster #${i}: invalid enabled status"
        errors=$(($errors+1))
    fi

    if [[ -z ${SLAVE_NAME[$index]} ]]; then
        log_failure_msg "buildmaster #${i}: no name"
        errors=$(($errors+1))
    fi

    if [[ -z ${SLAVE_USER[$index]} ]]; then
        log_failure_msg "buildmaster #${i}: no run user specified"
        errors=$( ($errors+1) )
    elif ! getent passwd ${SLAVE_USER[$index]} >/dev/null; then
        log_failure_msg "buildmaster #${i}: unknown user ${SLAVE_USER[$index]}"
        errors=$(($errors+1))
    fi

    if [[ ! -d "${SLAVE_BASEDIR[$index]}" ]]; then
        log_failure_msg "buildmaster ${i}: basedir does not exist ${SLAVE_BASEDIR[$index]}"
        errors=$(($errors+1))
    fi

    return $errors
}

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
        if is_disabled "${SLAVE_ENABLED[$i]}" ; then
            log_warning_msg "buildslave #${i}: disabled"
            continue
        fi
        slave_config_valid $i
        errors=$(($errors+$?))
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
        if is_disabled "${SLAVE_ENABLED[$i]}" ; then
            continue
        fi

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
