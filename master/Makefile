# developer utilities
pylint:
	pylint -j4 --rcfile=../common/pylintrc buildbot docs/*.py setup.py
	@test ! -f fail

tutorial:
	cd docs/tutorial; $(MAKE) html
flake8:
	flake8 --config=../common/flake8rc buildbot docs/*.py setup.py
rmpyc:
	make -C .. rmpyc
