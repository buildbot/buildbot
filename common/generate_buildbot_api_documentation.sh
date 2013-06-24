#!/bin/bash

cd /tmp
wget http://sourceforge.net/projects/epydoc/files/epydoc/3.0.1/epydoc-3.0.1.tar.gz
tar -xzf epydoc-3.0.1.tar.gz
cd epydoc-3.0.1
wget http://gentoo-progress.googlecode.com/svn/overlays/progress/dev-python/epydoc/files/epydoc-3.0.1-docutils-0.6.patch
wget http://gentoo-progress.googlecode.com/svn/overlays/progress/dev-python/epydoc/files/epydoc-3.0.1-python-2.6.patch
patch -p0 < epydoc-3.0.1-docutils-0.6.patch
patch -p0 < epydoc-3.0.1-python-2.6.patch

cd /tmp

wget http://pypi.python.org/packages/source/b/buildbot/buildbot-0.8.7.tar.gz
wget http://pypi.python.org/packages/source/b/buildbot-slave/buildbot-slave-0.8.7.tar.gz
tar -xzf buildbot-0.8.7.tar.gz
tar -xzf buildbot-slave-0.8.7.tar.gz

git clone https://github.com/buildbot/buildbot.git
cd buildbot/apidocs
PYTHONPATH="/tmp/epydoc-3.0.1:/tmp/buildbot-0.8.7:/tmp/buildbot-slave-0.8.7${PYTHONPATH:+:}${PYTHONPATH}" make
