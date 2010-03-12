# this is just a convenience for developers, and to automate the release
# process a little bit. This Makefile is not included in the source tarball.

BBBASE = $(PWD)
TRIALARGS=
ifdef SVN
T=~/stuff/python/twisted/Twisted
TRIALARGS=--reporter=verbose
else
T=
endif
ifdef T13
T=~/stuff/python/twisted/Twisted-1.3.0
TRIALARGS=-v
endif
PP = PYTHONPATH=$(BBBASE):$(T)

.PHONY: test
TRIAL=trial
TEST=buildbot.test
test:
	$(PP) $(TRIAL) $(TRIALARGS) $(TEST)

test-coverage:
	$(PP) $(TRIAL) --reporter=bwverbose-coverage $(TEST)

PYTHON=python
COVERAGE_OMIT = --omit /System,/Library,/usr/lib,buildbot/test,simplejson
coverage-output-text:
	$(PYTHON) contrib/coverage2text.py
coverage-output:
	rm -rf coverage-html
	coverage html -d coverage-html $(COVERAGE_OMIT)
	cp .coverage coverage-html/coverage.data
	@echo "now point your browser at coverage-html/index.html"


deb-snapshot:
	debchange --newversion `PYTHONPATH=. python -c "import buildbot; print buildbot.version"`.`date +%Y.%m.%d.%H.%M.%S` \
	 "snapshot build"
	debuild binary

.PHONY: docs apidocs some-apidocs paper
docs:
	$(MAKE) -C docs

apidocs:
	PYTHONPATH=.:$(T) python docs/epyrun -o docs/reference
some-apidocs:
	PYTHONPATH=.:$(T) python docs/epyrun -o docs/reference --modules $(EPYDOCS)
paper:
	$(MAKE) -C docs/PyCon-2003 all

release: docs
	chmod 0755 .
	find buildbot contrib docs -type d -exec chmod 0755 {} \;
	find bin buildbot contrib docs -type f -exec chmod 0644 {} \;
	chmod 0644 MANIFEST* NEWS README* setup.py
	chmod a+x bin/buildbot contrib/*.py contrib/windows/*.py
	rm -rf _trial_temp
	python ./setup.py clean
	rm -f MANIFEST
	python ./setup.py sdist --formats gztar,zip

FLAKES=buildbot
pyflakes:
	pyflakes $(FLAKES) |sort |uniq

