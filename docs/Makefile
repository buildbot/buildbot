all: docs.tgz

VERSION=$(shell python -c 'g = {}; execfile("../buildbot/__init__.py",g); print g["version"]')

buildbot.info: buildbot.texinfo
	echo "@set VERSION $(VERSION)" > version.texinfo
	makeinfo --fill-column=70 $<

buildbot.html: buildbot.texinfo images-png
	echo "@set VERSION $(VERSION)" > version.texinfo
	makeinfo --no-split --html $<

docs.tgz: buildbot.html images-png
	echo "@set VERSION $(VERSION)" > version.texinfo
	rm -rf $(VERSION)
	makeinfo --html --output $(VERSION) buildbot.texinfo
	cp buildbot.html $(VERSION)/full.html
	mkdir $(VERSION)/images
	cp images/*.png $(VERSION)/images
	tar -zcf $@ $(VERSION)

buildbot.ps: buildbot.texinfo images-eps
	echo "@set VERSION $(VERSION)" > version.texinfo
	rm -rf buildbot
	texi2dvi $<
	dvips buildbot.dvi
	rm buildbot.aux buildbot.cp buildbot.cps buildbot.fn buildbot.ky buildbot.log buildbot.pg buildbot.toc buildbot.tp buildbot.vr
	rm buildbot.dvi

.PHONY: images images-png images-eps
images:
	$(MAKE) -C images all
images-png:
	# rule disabled, since the .png's are in git
	#$(MAKE) -C images images-png
images-eps:
	$(MAKE) -C images images-eps
