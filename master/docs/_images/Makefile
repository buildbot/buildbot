
SOURCES = overview_src.svg changes_src.svg workers_src.svg master_src.svg multimaster_src.svg auth_rules_src.svg
SVGS = $(patsubst %_src.svg,%.svg,$(SOURCES))
PNGS = $(patsubst %_src.svg,%.png,$(SOURCES))

.PHONY: images-svg images-png images-eps
all: $(SVGS) $(PNGS) $(EPSS)
images-svg: $(SVGS)
images-png: $(PNGS)

# Source SVG files contains text labels in "Noto Sans" font which may not be
# installed on end user machine. Render these text labels into paths.
# "Noto Sans" font can be downloaded from Google Fonts collection.
%.svg: %_src.svg
	cp $< _tmp.svg
	# Render text as path.
	inkscape _tmp.svg --verb EditSelectAll --verb=ObjectToPath --verb FileSave --verb FileQuit
	# Cleanup SVG to reduce its size.
	scour --enable-comment-stripping --remove-metadata -i _tmp.svg -o $@
	rm -f _tmp.svg
%.png: %.svg
	inkscape -b white --export-png $@ $<
	mogrify -trim +repage $@
clean:
	rm -f $(PNGS) $(SVGS)
