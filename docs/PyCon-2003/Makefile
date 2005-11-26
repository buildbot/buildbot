LORE=lore
IMAGES = overview.png slave.png

all: buildbot.html images

buildbot.html: source/buildbot.lore source/template.tpl
	$(LORE) -p --config template=source/template.tpl $<
	mv source/buildbot.html $@

.PHONY: hlint
hlint: source/buildbot.lore
	$(LORE) --output lint $<

.PHONY: tarball
tarball: buildbot.html images
	rm -rf buildbot-pycon
	mkdir buildbot-pycon
	cp buildbot.html stylesheet.css buildbot-pycon/
	cp *.png buildbot-pycon/
	tar czf buildbot-pycon.tar.gz buildbot-pycon
	rm -rf buildbot-pycon

clean:
	rm -f buildbot.html $(IMAGES)

.PHONY: images
images: $(IMAGES) sizes

sizes:
	@for i in *.png; do \
	 echo $$i `pngtopnm $$i |pnmfile`; \
	done

%.png: source/%.svg
	inkscape --export-png $@ $<
