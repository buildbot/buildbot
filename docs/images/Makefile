
all: overview.png overview.eps slaves.png slaves.eps slavebuilder.png slavebuilder.eps master.png master.eps status.png status.eps

%.png: %.svg
	inkscape -b white --export-png $@ $<
%.eps: %.svg
	inkscape --export-eps $@ $<

clean:
	rm -f *.png *.eps
