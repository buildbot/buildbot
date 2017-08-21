# developer utilities
pylint:
	pylint -j4 --rcfile=../common/pylintrc buildbot
	pylint -j4 --rcfile=../common/pylintrc docs/conf.py
tutorial:
	cd docs/tutorial; $(MAKE) html
flake8:
	flake8 --config=../common/flake8rc buildbot
	flake8 --config=../common/flake8rc docs/conf.py
rmpyc:
	make -C .. rmpyc
