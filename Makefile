# developer utilities

.PHONY: docs apidocs pylint artifacts

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
	pep8 --config=common/pep8rc master slave

# TODO(sa2ajj): make it a non-phony target
artifacts: DEST_DIR := $(CURDIR)/dist
artifacts:
	@rm -rf $(DEST_DIR)
	@mkdir -p $(DEST_DIR)
	@for name in master slave; do (rm -f $$name/MANIFEST; cd $$name; python setup.py sdist --formats gztar,zip -d $(DEST_DIR)); done

rmpyc:
	find . \( -name '*.pyc' -o -name '*.pyo' \) -exec rm -v {} \;
