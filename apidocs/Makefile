.PHONY: all reference cleanpyc

all: reference.tgz

cleanpyc:
	cd .. && find master slave -name '*.pyc' -exec rm \{} \; || exit 1

reference: cleanpyc
	rm -rf reference
	cd .. && python apidocs/epyrun -o apidocs/reference \
			--exclude="buildbot\\.test" --exclude="buildslave\\.test" \
			buildbot buildslave

reference.tgz: reference
	tar -zcf reference.tgz reference
