
SOURCES = overview.svg slaves.svg slavebuilder.svg master.svg status.svg
PNGS = $(patsubst %.svg,%.png,$(SOURCES))
EPSS = $(patsubst %.svg,%.eps,$(SOURCES))

.PHONY: images-png images-eps
all: $(PNGS) $(EPSS)
images-png: $(PNGS)
images-eps: $(EPSS)

%.png: %.svg
	inkscape -b white --export-png $@ $<
%.eps: %.svg
	inkscape --export-eps $@ $<

clean:
	rm -f *.png *.eps
