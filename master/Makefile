# developer utilities
pylint:
	pylint -j4 --rcfile=../common/pylintrc buildbot
	@test ! -f fail

tutorial:
	cd docs/tutorial; $(MAKE) html
flake8:
	flake8 --config=../common/flake8rc buildbot
	flake8 --config=../common/flake8rc docs/conf.py
rmpyc:
	make -C .. rmpyc
