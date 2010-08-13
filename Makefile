# developer utilities

.PHONY: docs apidocs some-apidocs paper
docs:
	$(MAKE) -C master/docs

apidocs:
	$(MAKE) -C apidocs

pylint:
	cd master; $(MAKE) pylint
	cd slave; $(MAKE) pylint
