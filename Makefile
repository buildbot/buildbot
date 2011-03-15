# developer utilities

.PHONY: docs apidocs pylint

docs:
	$(MAKE) -C master/docs

apidocs:
	$(MAKE) -C apidocs

tutorial:
	$(MAKE) -C master/docs tutorial

pylint:
	cd master; $(MAKE) pylint
	cd slave; $(MAKE) pylint

pyflakes:
	pyflakes master/buildbot slave/buildslave
