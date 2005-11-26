
# this is just a convenience for developers, and to automate the release
# process a little bit. This Makefile is not included in the source tarball.

BBBASE = $(PWD)
TRIALARGS=-v
ifdef SVN
T=~/stuff/python/twisted/Twisted
TRIALARGS=--reporter=verbose
else
T=
endif
ifdef T13
T=~/stuff/python/twisted/Twisted-1.3.0
endif
PP = PYTHONPATH=$(BBBASE):$(T)

.PHONY: test
TRIAL=trial
TEST=buildbot.test
test:
	$(PP) $(TRIAL) $(TRIALARGS) $(TEST)


#debuild -uc -us

deb-snapshot:
	debchange --newversion `PYTHONPATH=. python -c "import buildbot; print buildbot.version"`.`date +%Y.%m.%d.%H.%M.%S` \
	 "snapshot build"
	debuild binary

.PHONY: docs apidocs paper
docs:
	$(MAKE) -C docs buildbot.info
apidocs:
	PYTHONPATH=.:$(T) python docs/epyrun -o docs/reference
paper:
	$(MAKE) -C docs/PyCon-2003 all

release: docs paper
	chmod 0755 .
	find buildbot contrib docs -type d -exec chmod 0755 {} \;
	find bin buildbot contrib docs -type f -exec chmod 0644 {} \;
	chmod 0644 ChangeLog MANIFEST* NEWS README* setup.py
	chmod a+x bin/buildbot contrib/*.py
	rm -rf _trial_temp
	python ./setup.py clean
	rm -f MANIFEST
	python ./setup.py sdist
