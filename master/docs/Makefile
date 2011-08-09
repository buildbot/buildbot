all: docs.tgz

.PHONY: images images-png images-eps tutorial manual

VERSION=$(shell if [ -n "$$VERSION" ]; then echo $$VERSION; else PYTHONPATH=..:$${PYTHONPATH} python -c 'from buildbot import version; print version'; fi)

docs.tgz: manual images-png
	fail # this rule is still TODO..
	echo "@set VERSION $(VERSION)" > version.texinfo
	rm -rf $(VERSION)
	makeinfo --html --output $(VERSION) buildbot.texinfo
	cp buildbot.html $(VERSION)/full.html
	mkdir $(VERSION)/images
	cp images/*.png $(VERSION)/images
	tar -zcf $@ $(VERSION)

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
