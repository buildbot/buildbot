
SOURCES = overview.svg slaves.svg master.svg status.svg
PNGS = $(patsubst %.svg,%.png,$(SOURCES))
EPSS = $(patsubst %.svg,%.eps,$(SOURCES))

.PHONY: images-png images-eps
all: $(PNGS) $(EPSS)
images-png: $(PNGS)
images-eps: $(EPSS)

%.png: %.svg
	inkscape -b white --export-png $@ $<
	mogrify -trim +repage $@
%.eps: %.svg
	inkscape --export-eps $@ $<
	mogrify -trim +repage $@
clean:
	rm -f *.png *.eps
