# developer utilities

all: test pylint pyflakes

test:
	trial buildslave

pylint:
	pylint --rcfile=../common/pylintrc buildslave

pyflakes:
	pyflakes buildslave
