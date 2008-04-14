
buildbot.info: buildbot.texinfo
	makeinfo --fill-column=70 $<

#images-png
buildbot.html: buildbot.texinfo
	makeinfo --no-split --html $<

#images-eps
buildbot.ps: buildbot.texinfo
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
