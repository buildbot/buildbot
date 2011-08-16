# developer utilities

.PHONY: docs apidocs pylint

docs:
	$(MAKE) -C master/docs

apidocs:
	$(MAKE) -C apidocs

pylint:
	cd master; $(MAKE) pylint
	cd slave; $(MAKE) pylint

pyflakes:
	pyflakes master/buildbot slave/buildslave
