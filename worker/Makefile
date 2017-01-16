# developer utilities
pylint:
	pylint --rcfile=../common/pylintrc \
	    --spelling-private-dict-file ../common/code_spelling_ignore_words.txt \
	    buildbot_worker

flake8:
	flake8 --config=../common/flake8rc buildbot_worker
