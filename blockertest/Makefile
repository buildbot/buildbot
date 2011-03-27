VIRTUALENV = /usr/local/buildbot
BUILDBOT := $(VIRTUALENV)/bin/buildbot
BUILDSLAVE := $(VIRTUALENV)/bin/buildslave

.PHONY: default start stop wipelogs hard-stop hard-restart
.PHONY: setup master slaves clean

default:
	@echo "No default target here.  Choices: 'start', 'stop', 'hard-stop', 'hard-restart'." 2>&1

start: master slaves
	$(BUILDBOT) start master
	$(BUILDSLAVE) start -q slaveA
	$(BUILDSLAVE) start -q slaveB

stop:
	-$(BUILDBOT) stop -q master
	-$(BUILDSLAVE) stop -q slaveA
	-$(BUILDSLAVE) stop -q slaveB

wipelogs:
	rm -rf master/builder[0-9]*[AB]
	cat /dev/null > master/twistd.log

reconfig:
	$(BUILDBOT) reconfig master

restart: stop start

hard-stop: stop wipelogs

hard-restart: stop wipelogs start

setup: master slaves

master: master/.stamp

master/.stamp:
	$(BUILDBOT) create-master master
	(cd master && ln -s ../master.cfg . && rm -f *.sample)
	touch master/twistd.log
	touch $@

slaves: slaveA/.stamp slaveB/.stamp

slaveA/.stamp:
	$(BUILDSLAVE) create-slave slaveA localhost:9989 slaveA slaveA
	touch $@

slaveB/.stamp:
	$(BUILDSLAVE) create-slave slaveB localhost:9989 slaveB slaveB
	touch $@

clean: check-stopped force-clean

check-stopped:
	@[ ! -f master/twistd.pid -a ! -f slaveA/twistd.pid -a ! -f slaveB/twistd.pid ] || \
	  ( echo -e \
	      "error: at least one daemon seems to be running still" \
	      "\n(use 'make stop' to stop them, or 'make force-clean' if you know what you are doing)" >&2 ; \
	    false )

force-clean:
	rm -rf master slaveA slaveB .*stamp
