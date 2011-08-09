all: docs.tgz

.PHONY: images images-png images-eps tutorial manual

VERSION=$(shell if [ -n "$$VERSION" ]; then echo $$VERSION; else PYTHONPATH=..:$${PYTHONPATH} python -c 'from buildbot import version; print version'; fi)

docs.tgz: manual images-png
	cd manual; $(MAKE) singlehtml
	cp manual/_build/singlehtml/index.html manual/_build/html/full.html
	tar -C manual/_build --transform 's/^html/$(VERSION)/' -zcf $@ html

images:
	$(MAKE) -C images all
images-png:
	# rule disabled, since the .png's are in git
	#$(MAKE) -C images images-png
images-eps:
	$(MAKE) -C images images-eps

manual:
	cd manual; $(MAKE) clean; $(MAKE) html

tutorial:
	cd tutorial; $(MAKE) clean; $(MAKE) html
