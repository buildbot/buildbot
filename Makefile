# developer utilities

.PHONY: docs apidocs pylint

PIP?=pip

# build rst documentation
docs:
	$(MAKE) -C master/docs

# create api documentation with epydoc
apidocs:
	$(MAKE) -C apidocs

# pylint the whole sourcecode (validate.sh will do that as well, but only process the modified files)
pylint:
	$(MAKE) -C master pylint; master_res=$$?; \
	$(MAKE) -C slave pylint; slave_res=$$?; \
	if [ $$master_res != 0 ] || [ $$slave_res != 0 ]; then exit 1; fi

# pyflakes the whole sourcecode (validate.sh will do that as well, but only process the modified files)
pyflakes:
	pyflakes master/buildbot slave/buildslave

# pep8 the whole sourcecode (validate.sh will do that as well, but only process the modified files)
pep8:
	pep8 --config=common/pep8rc master/buildbot slave/buildslave www/*/buildbot_*/ www/*/setup.py

# rebuild front-end from source
frontend:
	$(PIP) install -e pkg
	$(PIP) install mock
	for i in base codeparameter console_view waterfall_view nestedexample; do $(PIP) install -e www/$$i ; done

# do installation tests. Test front-end can build and install for all install methods
frontend_install_tests:
	$(PIP) install -e pkg
	$(PIP) install mock wheel
	trial pkg/test_buildbot_pkg.py

prebuilt_frontend:
	$(PIP) install -U http://ftp.buildbot.net/pub/latest/buildbot_www-1latest-py2-none-any.whl
	$(PIP) install -U http://ftp.buildbot.net/pub/latest/buildbot_codeparameter-1latest-py2-none-any.whl
	$(PIP) install -U http://ftp.buildbot.net/pub/latest/buildbot_console_view-1latest-py2-none-any.whl
	$(PIP) install -U http://ftp.buildbot.net/pub/latest/buildbot_waterfall_view-1latest-py2-none-any.whl

# install git hooks for validating patches at commit time
hooks:
	cp common/hooks/* `git rev-parse --git-dir`/hooks

rmpyc:
	find . \( -name '*.pyc' -o -name '*.pyo' \) -exec rm -v {} \;
