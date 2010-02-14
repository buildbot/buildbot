
buildbot.info: buildbot.texinfo
	python version.py > version.texinfo
	makeinfo --fill-column=70 $<

buildbot.html: buildbot.texinfo images-png
	python version.py > version.texinfo
	makeinfo --no-split --html $<

buildbot: buildbot.texinfo images-png
	python version.py > version.texinfo
	makeinfo --html $<

buildbot.ps: buildbot.texinfo images-eps
	python version.py > version.texinfo
	texi2dvi $<
	dvips buildbot.dvi
	rm buildbot.aux buildbot.cp buildbot.cps buildbot.fn buildbot.ky buildbot.log buildbot.pg buildbot.toc buildbot.tp buildbot.vr
	rm buildbot.dvi

.PHONY: images images-png images-eps
images:
	$(MAKE) -C images all
images-png:
	$(MAKE) -C images images-png
images-eps:
	$(MAKE) -C images images-eps
