# developer utilities
pylint:
	pylint --rcfile=../common/pylintrc \
	    --spelling-private-dict-file ../common/code_spelling_ignore_words.txt \
			buildbot
	pylint --rcfile=../common/pylintrc \
	    --spelling-private-dict-file ../common/code_spelling_ignore_words.txt \
	    docs/conf.py
tutorial:
	cd docs/tutorial; $(MAKE) html
flake8:
	flake8 --config=../common/flake8rc buildbot
	flake8 --config=../common/flake8rc docs/conf.py
rmpyc:
	make -C .. rmpyc
