
buildbot.info: buildbot.texinfo
	makeinfo --fill-column=70 $<

buildbot.html: buildbot.texinfo
	makeinfo --no-split --html $<

buildbot.ps: buildbot.texinfo
	texi2dvi $<
	dvips buildbot.dvi
	rm buildbot.aux buildbot.cp buildbot.cps buildbot.fn buildbot.ky buildbot.log buildbot.pg buildbot.toc buildbot.tp buildbot.vr
	rm buildbot.dvi


