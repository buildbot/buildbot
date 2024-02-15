# developer utilities
pylint:
	pylint -j4 --rcfile=../common/pylintrc buildbot docs/*.py setup.py
	@test ! -f fail

tutorial:
	cd docs/tutorial; $(MAKE) html

rmpyc:
	make -C .. rmpyc
