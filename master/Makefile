# developer utilities
pylint:
	pylint --rcfile=../common/pylintrc buildbot
tutorial:
	cd docs/tutorial; $(MAKE) html
flake8:
	flake8 --config=../common/flake8rc buildbot
rmpyc:
	make -C .. rmpyc
