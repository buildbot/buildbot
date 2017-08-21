# developer utilities
pylint:
	@rm -f pylint.fail
	find buildbot -maxdepth 1 -mindepth 1 |egrep -v '(png|pyc|newsfra)'  |sed 's|/|.|' |sed 's|.py$$||'| while read module ;\
	do \
		echo $$module ;\
		pylint --rcfile=../common/pylintrc $$module || echo > pylint.fail ;\
	done
	pylint --rcfile=../common/pylintrc docs/conf.py
	@test ! -f fail

tutorial:
	cd docs/tutorial; $(MAKE) html
flake8:
	flake8 --config=../common/flake8rc buildbot
	flake8 --config=../common/flake8rc docs/conf.py
rmpyc:
	make -C .. rmpyc
