# developer utilities
DOCKERBUILD := docker build --build-arg http_proxy=$$http_proxy --build-arg https_proxy=$$https_proxy

.PHONY: docs pylint flake8 virtualenv


VENV_NAME:=.venv$(VENV_PY_VERSION)
PIP?=$(VENV_NAME)/bin/pip
VENV_PY_VERSION?=python

WWW_PKGS := pkg www/base www/console_view www/grid_view www/waterfall_view www/wsgi_dashboards
WWW_EX_PKGS := nestedexample codeparameter
ALL_PKGS := master worker $(WWW_PKGS)

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

frontend_deps: $(VENV_NAME)
	$(PIP) install -e pkg
	$(PIP) install mock wheel buildbot

# rebuild front-end from source
frontend: frontend_deps
	for i in $(WWW_PKGS) $(WWW_EX_PKG); do $(PIP) install -e $$i || exit 1; done

# do installation tests. Test front-end can build and install for all install methods
frontend_install_tests: frontend_deps
	trial pkg/test_buildbot_pkg.py

# install git hooks for validating patches at commit time
hooks:
	cp common/hooks/* `git rev-parse --git-dir`/hooks
rmpyc:
	find . \( -name '*.pyc' -o -name '*.pyo' \) -exec rm -v {} \;

isort:
	isort -rc worker master
	git diff --name-only --stat "HEAD" | grep '.py$$' | xargs autopep8 -i
	git commit -a -m "isort+autopep8 run"


docker: docker-buildbot-worker docker-buildbot-worker-node docker-buildbot-master docker-buildbot-master-ubuntu
	echo done
docker-buildbot-worker:
	$(DOCKERBUILD) -t buildbot/buildbot-worker:master worker
docker-buildbot-master:
	$(DOCKERBUILD) -t buildbot/buildbot-master:master master
docker-buildbot-master-ubuntu:
	$(DOCKERBUILD) -t buildbot/buildbot-master-ubuntu:master -f master/Dockerfile.ubuntu master

$(VENV_NAME):
	virtualenv -p $(VENV_PY_VERSION) $(VENV_NAME)
	$(PIP) install -U pip setuptools

# helper for virtualenv creation
virtualenv: $(VENV_NAME)   # usage: make virtualenv VENV_PY_VERSION=python3.4
	@echo now you can type following command  to activate your virtualenv
	@echo . $(VENV_NAME)/bin/activate
	$(PIP) install -e pkg \
		-e 'master[tls,test,docs]' \
		-e 'worker[test]' \
		buildbot_www packaging \
		'git+https://github.com/tardyp/towncrier'

release_notes: $(VENV_NAME)
	test ! -z "$(VERSION)"  #  usage: make release_notes VERSION=0.9.2
	yes | towncrier --version $(VERSION) --date `date -u  +%F`
	git commit -m "relnotes for $(VERSION)"

$(ALL_PKGS_TARGETS): cleanup_for_tarballs frontend_deps
	. .venv/bin/activate && ./common/maketarball.sh $(patsubst %_pkg,%,$@)

cleanup_for_tarballs:
	find . -name VERSION -exec rm {} \;
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
	test -d "../bbdocs/.git"  #  make release shoud be done with bbdocs populated at the same level as buildbot dir
	GPG_TTY=`tty` git tag -a -sf v$(VERSION) -m "TAG $(VERSION)"
	make -j4 tarballs
	./common/smokedist.sh
	export VERSION=$(VERSION) ; . .venv/bin/activate && make docs
	rm -rf ../bbdocs/docs/$(VERSION)  # in case of re-run
	cp -r master/docs/_build/html ../bbdocs/docs/$(VERSION)
	. .venv/bin/activate && cd ../bbdocs && make && git add . && git commit -m $(VERSION) && git push
	echo twine upload --sign dist/*
