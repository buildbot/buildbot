# developer utilities
pylint:
	pylint -j4 --rcfile=../common/pylintrc_worker --disable=super-with-arguments,raise-missing-from buildbot_worker setup.py

flake8:
	flake8 --config=../common/flake8rc buildbot_worker setup.py
