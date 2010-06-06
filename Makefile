# developer utilities

.PHONY: docs apidocs some-apidocs paper
docs:
	$(MAKE) -C docs

reference:
	cd docs; ./gen-reference

pylint:
	cd master; $(MAKE) pylint
	cd slave; $(MAKE) pylint
