# developer utilities

.PHONY: docs apidocs pylint

PIP?=pip

docs:
	$(MAKE) -C master/docs

apidocs:
	$(MAKE) -C apidocs

pylint:
	$(MAKE) -C master pylint; master_res=$$?; \
	$(MAKE) -C slave pylint; slave_res=$$?; \
	if [ $$master_res != 0 ] || [ $$slave_res != 0 ]; then exit 1; fi

pyflakes:
	pyflakes master/buildbot slave/buildslave

pep8:
	pep8 --config=common/pep8rc master/buildbot slave/buildslave www/*/buildbot_*/ www/*/setup.py

frontend:
	$(PIP) install -e pkg
	$(PIP) install mock
	for i in www/*/; do $(PIP) install -e $$i ; done

frontend_install_tests:
	$(PIP) install -e pkg
	$(PIP) install mock wheel
	trial pkg/test_buildbot_pkg.py

rmpyc:
	find . \( -name '*.pyc' -o -name '*.pyo' \) -exec rm -v {} \;
