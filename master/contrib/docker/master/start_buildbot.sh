#!/bin/sh

# startup script for purely stateless master

# we download the config from an arbitrary curl accessible tar.gz file (which github can generate for us)

B=`pwd`

if [ -z "$BUILDBOT_CONFIG_URL" ]
then
    if [ ! -f "$B/master.cfg" ]
    then
        echo No master.cfg found nor $$BUILDBOT_CONFIG_URL !
        echo Please provide a master.cfg file in $B or provide a $$BUILDBOT_CONFIG_URL variable via -e
        exit 1
    fi

else
    BUILDBOT_CONFIG_DIR=${BUILDBOT_CONFIG_DIR:-config}
    mkdir -p $B/$BUILDBOT_CONFIG_DIR
    # if it ends with .tar.gz then its a tarball, else its directly the file
    if echo "$BUILDBOT_CONFIG_URL" | grep '.tar.gz$' >/dev/null
    then
        until curl -sL $BUILDBOT_CONFIG_URL | tar -xz --strip-components=1 --directory=$B/$BUILDBOT_CONFIG_DIR
        do
            echo "Can't download from \$BUILDBOT_CONFIG_URL: $BUILDBOT_CONFIG_URL"
            sleep 1
        done

        ln -sf $B/$BUILDBOT_CONFIG_DIR/master.cfg $B/master.cfg

        if [ -f $B/$BUILDBOT_CONFIG_DIR/buildbot.tac ]
        then
            ln -sf $B/$BUILDBOT_CONFIG_DIR/buildbot.tac $B/buildbot.tac
        fi
    else
        until curl -sL $BUILDBOT_CONFIG_URL > $B/master.cfg
        do
            echo "Can't download from $$BUILDBOT_CONFIG_URL: $BUILDBOT_CONFIG_URL"
        done
    fi
fi
# copy the default buildbot.tac if not provided by the config
if [ ! -f $B/buildbot.tac ]
then
    cp /usr/src/buildbot/contrib/docker/master/buildbot.tac $B
fi
# wait for db to start by trying to upgrade the master
until buildbot upgrade-master $B
do
    echo "Can't upgrade master yet. Waiting for database ready?"
    sleep 1
done

# we use exec so that twistd use the pid 1 of the container, and so that signals are properly forwarded
exec twistd -ny $B/buildbot.tac
