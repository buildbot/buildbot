# developer utilities
DOCKERBUILD := docker build --build-arg http_proxy=$$http_proxy --build-arg https_proxy=$$https_proxy

.PHONY: docs pylint flake8 virtualenv


VENV_NAME:=.venv$(VENV_PY_VERSION)
PIP?=$(VENV_NAME)/bin/pip
VENV_PY_VERSION?=python3

WWW_PKGS := www/base www/console_view www/grid_view www/waterfall_view www/wsgi_dashboards www/badges
WWW_EX_PKGS := www/nestedexample www/codeparameter
WWW_DEP_PKGS := www/guanlecoja-ui www/data_module
ALL_PKGS := master worker pkg $(WWW_PKGS)

WWW_PKGS_FOR_UNIT_TESTS := $(filter-out www/badges, $(WWW_DEP_PKGS) $(WWW_PKGS))

ALL_PKGS_TARGETS := $(addsuffix _pkg,$(ALL_PKGS))
.PHONY: $(ALL_PKGS_TARGETS)

# build rst documentation
docs:
	$(MAKE) -C master/docs

# check rst documentation
docschecks:
	$(MAKE) -C master/docs SPHINXOPTS=-W spelling
	$(MAKE) -C master/docs SPHINXOPTS=-q linkcheck

# pylint the whole sourcecode (validate.sh will do that as well, but only process the modified files)
pylint:
	$(MAKE) -C master pylint; master_res=$$?; \
	$(MAKE) -C worker pylint; worker_res=$$?; \
	if [ $$master_res != 0 ] || [ $$worker_res != 0 ]; then exit 1; fi

# flake8 the whole sourcecode (validate.sh will do that as well, but only process the modified files)
flake8:
	$(MAKE) -C master flake8
	$(MAKE) -C worker flake8
	flake8 --config=common/flake8rc www/*/buildbot_*/
	flake8 --config=common/flake8rc www/*/setup.py
	flake8 --config=common/flake8rc common/*.py

frontend_deps: $(VENV_NAME)
	$(PIP) install -e pkg
	$(PIP) install mock wheel buildbot
	cd www/build_common; yarn install --pure-lockfile
	for i in $(WWW_DEP_PKGS); \
		do (cd $$i; yarn install --pure-lockfile; yarn run build); done

frontend_tests: frontend_deps
	for i in $(WWW_PKGS); \
		do (cd $$i; yarn install --pure-lockfile); done
	for i in $(WWW_PKGS_FOR_UNIT_TESTS); \
		do (cd $$i; yarn run build-dev || exit 1; yarn run test || exit 1) || exit 1; done

frontend_tests_headless: frontend_deps
	for i in $(WWW_PKGS); \
		do (cd $$i; yarn install --pure-lockfile); done
	for i in $(WWW_PKGS_FOR_UNIT_TESTS); \
		do (cd $$i; yarn run build-dev || exit 1; yarn run test --browsers BBChromeHeadless || exit 1) || exit 1; done

# rebuild front-end from source
frontend: frontend_deps
	for i in pkg $(WWW_PKGS); do $(PIP) install -e $$i || exit 1; done

# do installation tests. Test front-end can build and install for all install methods
frontend_install_tests: frontend_deps
	trial pkg/test_buildbot_pkg.py

# upgrade FE dependencies
frontend_yarn_upgrade:
	for i in $(WWW_PKGS) $(WWW_EX_PKGS) $(WWW_DEP_PKGS); \
		do (cd $$i; echo $$i; rm -rf yarn.lock; yarn install || echo $$i failed); done

# install git hooks for validating patches at commit time
hooks:
	cp common/hooks/* `git rev-parse --git-dir`/hooks
rmpyc:
	find master worker \( -name '*.pyc' -o -name '*.pyo' \) -exec rm -v {} \;

isort:
	isort -rc worker master
	git diff --name-only --stat "HEAD" | grep '.py$$' | xargs autopep8 -i
	git commit -a -m "isort+autopep8 run"


docker: docker-buildbot-worker docker-buildbot-master
	echo done
docker-buildbot-worker:
	$(DOCKERBUILD) -t buildbot/buildbot-worker:master worker
docker-buildbot-master:
	$(DOCKERBUILD) -t buildbot/buildbot-master:master master

$(VENV_NAME):
	virtualenv -p $(VENV_PY_VERSION) $(VENV_NAME)
	$(PIP) install -U pip setuptools

# helper for virtualenv creation
virtualenv: $(VENV_NAME)   # usage: make virtualenv VENV_PY_VERSION=python3.4
	$(PIP) install -e pkg \
		-e 'master[tls,test,docs]' \
		-e 'worker[test]' \
		buildbot_www packaging towncrier
	@echo now you can type following command  to activate your virtualenv
	@echo . $(VENV_NAME)/bin/activate

TRIALOPTS?=buildbot

.PHONY: trial
trial: virtualenv
	. $(VENV_NAME)/bin/activate && trial $(TRIALOPTS)

release_notes: $(VENV_NAME)
	test ! -z "$(VERSION)"  #  usage: make release_notes VERSION=0.9.2
	yes | towncrier --version $(VERSION) --date `date -u  +%F`
	git commit -m "relnotes for $(VERSION)"

$(ALL_PKGS_TARGETS): cleanup_for_tarballs frontend_deps
	. $(VENV_NAME)/bin/activate && ./common/maketarball.sh $(patsubst %_pkg,%,$@)

cleanup_for_tarballs:
	find master pkg worker www -name VERSION -exec rm {} \;
	rm -rf dist
	mkdir dist
.PHONY: cleanup_for_tarballs
tarballs: $(ALL_PKGS_TARGETS)
.PHONY: tarballs


clean:
	git clean -xdf
# helper for release creation
release: virtualenv
	test ! -z "$(VERSION)"  #  usage: make release VERSION=0.9.2
	test -d "../bbdocs/.git"  #  make release should be done with bbdocs populated at the same level as buildbot dir
	GPG_TTY=`tty` git tag -a -sf v$(VERSION) -m "TAG $(VERSION)"
	git push buildbot "v$(VERSION)"  # tarballs are made by circleci.yml, and create a github release
	export VERSION=$(VERSION) ; . .venv/bin/activate && make docs
	rm -rf ../bbdocs/docs/$(VERSION)  # in case of re-run
	cp -r master/docs/_build/html ../bbdocs/docs/$(VERSION)
	cd ../bbdocs && git pull
	. .venv/bin/activate && cd ../bbdocs && make && git add . && git commit -m $(VERSION) && git push
	@echo When tarballs have been generated by circleci:
	@echo make finishrelease

finishrelease:
	rm -rf dist
	python3 ./common/download_release.py
	rm -rf ./dist/v*
	./common/smokedist.sh
	twine upload --sign dist/*

pyinstaller: virtualenv
	$(PIP) install pyinstaller
	$(VENV_NAME)/bin/pyinstaller -F pyinstaller/buildbot-worker.spec
