
SOURCES = overview_src.svg slaves_src.svg master_src.svg status_src.svg
SVGS = $(patsubst %_src.svg,%.svg,$(SOURCES))
PNGS = $(patsubst %_src.svg,%.png,$(SOURCES))
EPSS = $(patsubst %_src.svg,%.eps,$(SOURCES))

.PHONY: images-svg images-png images-eps
all: $(SVGS) $(PNGS) $(EPSS)
images-svg: $(SVGS)
images-png: $(PNGS)
images-eps: $(EPSS)

# Source SVG files contains text labels in "PT Sans" font which may not be
# installed on end user machine (originally text was in proprietary
# "Myriad Pro" font, "PT Sans" was chosen to replace it due to its visual
# similarity).
# Render these text labels into paths.
# "PT Sans" font can be downloaded from developer official site:
# <http://www.paratype.com/public/> or from Google Fonts collection.
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
%.eps: %.svg
	inkscape --export-eps $@ $<
	mogrify -trim +repage $@
clean:
	rm -f *.png *.eps overview.svg slaves.svg master.svg status.svg
