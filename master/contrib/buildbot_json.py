#!/usr/bin/env python
# Copyright (c) 2011 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file at
# http://src.chromium.org/viewvc/chrome/trunk/src/LICENSE
# This file is NOT under GPL.

"""Queries buildbot through the json interface.

Example:
  ./buildbot_json.py http://build.chromium.org/p/tryserver.chromium -b linux --step compile
  Find all slaves on builder 'linux' which last build failed on compile step.
"""

__author__ = 'maruel@chromium.org'
__version__ = '1.0'

import datetime
import json
import logging
import optparse
import pprint
import time
import urllib
import sys


class Node(object):
    def __init__(self, parent, url):
        self.parent = parent
        self.url = url

    def read(self, suburl):
        return self.parent.read(self.url + str(suburl))


class NodeList(Node):
    _child_cls = None

    def __init__(self, parent, url):
        super(NodeList, self).__init__(parent, url)
        self._cache = {}
        # Keeps the keys independently when ordering is needed.
        self._keys = []
        self._cached = False
        self._keys_cached = False

    @property
    def keys(self):
        self.cache_keys()
        return self._keys

    def __getitem__(self, key):
        if not key in self._cache:
            if not self._keys_cached:
                # Assume it's valid for speed purpose.
                self._cache[key] = self._child_cls(self, key, None)
            else:
                raise StopIteration()
        return self._cache[key]

    def cache_keys(self):
        """Implement to speed up enumeration. Defaults to call cache()."""
        if not self._keys_cached:
            self.cache()
            self._keys_cached = True

    def cache(self):
        if not self._cached:
            data = self._readall()
            for k in sorted(data.iterkeys()):
                obj = self._child_cls(self, k, data[k])
                self._cache[obj.key] = obj
                if not obj.key in self._keys:
                    self._keys.append(obj.key)
            self._cached = True
            self._keys_cached = True

    def _readall(self):
        return self.read('')


class Slave(Node):
    def __init__(self, parent, name, data):
        super(Slave, self).__init__(parent, name + '/')
        self.name = name
        self.key = self.name
        self._data = data or {}

    @property
    def data(self):
        if not self._data:
            self._data.update(self.read(''))
        return self._data


class Slaves(NodeList):
    _child_cls = Slave
    # TODO(maruel): Implement cache_keys()

    def __init__(self, parent):
        super(Slaves, self).__init__(parent, 'slaves/')

    @property
    def names(self):
        return self.keys


class BuilderSlaves(NodeList):
    """Similar to Slaves but only list slaves connected to a specific builder.
    """
    _child_cls = Slave

    def __init__(self, parent):
        super(BuilderSlaves, self).__init__(parent, None)

    def cache(self):
        if not self._cached:
            for slave in self.parent.data['slaves']:
                # Set Slaves as parent.
                obj = self._child_cls(
                    self.parent.parent.parent.slaves, slave, None)
                self._cache[obj.key] = obj
                if not obj.key in self._keys:
                    self._keys.append(obj.key)
            self._cached = True
            self._keys_cached = True

    @property
    def names(self):
        return self.keys


class BuildStep(Node):
    def __init__(self, parent, number, data):
        super(BuildStep, self).__init__(parent, None)
        self.data = data
        self.number = number

    @property
    def key(self):
        return self.number

    @property
    def name(self):
        return self.data ['name']

    @property
    def result(self):
        data = self.data.get('results', [None])[0]
        if isinstance(data, list):
            data = data[0]
        return data


class BuildSteps(NodeList):
    _child_cls = BuildStep

    def __init__(self, parent, data):
        super(BuildSteps, self).__init__(parent, None)
        self._cached = True
        self._keys_cached = True
        for index, item in enumerate(data):
            obj = self._child_cls(self, index, item)
            # Support both step number and step name.
            self._cache[index] = obj
            self._cache[obj.name] = obj
        self._keys = sorted(self._cache.iterkeys())

    @property
    def properties(self):
        return self._data['properties']


class Build(Node):
    def __init__(self, parent, key, data):
        super(Build, self).__init__(parent, str(key))
        self._data = data or {'number': key}
        self._steps = BuildSteps(self, self._data.get('steps', []))

    def refresh(self):
        """Refreshes the data, only when result is None."""
        if self.result is None:
            self._data.update(self.read(''))

    @property
    def number(self):
        return int(self.data['number'])

    @property
    def key(self):
        return self.number

    @property
    def blamelist(self):
        return self.data['blame']

    @property
    def result(self):
        return self.data.get('results', None)

    @property
    def steps(self):
        return self._steps

    @property
    def slave(self):
        """Returns the slave object."""
        # Go up the hierarchy to find Slaves
        return self.parent.parent.parent.parent.slaves[self.data['slave']]

    def __str__(self):
        return pprint.pformat(self.data)

    @property
    def data(self):
        if not 'slave' in self._data:
            self._data.update(self.read(''))
            self._steps = BuildSteps(self, self._data['steps'])
        return self._data


class Builds(NodeList):
    _child_cls = Build
    def __init__(self, parent):
        super(Builds, self).__init__(parent, 'builds/')

    def refresh(self):
        """Refreshes cached builds."""
        self.parent.refresh()

    def __iter__(self):
        self.cache_keys()
        for k in reversed(self._keys):
            yield self[k]

    def __getitem__(self, key):
        key = int(key)
        if key < 0:
            # Convert negative to positive build number.
            self.cache_keys()
            key = self._keys[key]
        if not key in self._cache and not self._cached:
            # Assume it's valid for speed purpose.
            self._cache[key] = self._child_cls(self, key, None)
        return self._cache[key]

    def cache_keys(self):
        # Grab it from the builder.
        for i in self.parent.data['cachedBuilds']:
            i = int(i)
            self._cache.setdefault(i, Build(self, i, None))
            if not i in self._keys:
                self._keys.append(i)
        self._keys_cached = True

    def _readall(self):
        return self.read('_all')


class Builder(Node):
    def __init__(self, parent, name, data):
        """Data is pre-cached data."""
        super(Builder, self).__init__(parent, name + '/')
        self.name = name
        self._builds = Builds(self)
        self._data = data or {}
        self._slaves = BuilderSlaves(self)

    def refresh(self):
        """Refreshes cached builds."""
        self._data.update(self.read(''))
        self.builds.cache_keys()

    @property
    def key(self):
        return self.name

    @property
    def builds(self):
        return self._builds

    @property
    def slaves(self):
        return self._slaves

    @property
    def pendingBuilds(self):
        # Never cache this.
        return self.read('pendingBuilds')

    @property
    def data(self):
        if not self._data:
            self.refresh()
        return self._data


class Builders(NodeList):
    _child_cls = Builder
    # TODO(maruel): Implement cache_keys()

    def __init__(self, parent):
        super(Builders, self).__init__(parent, 'builders/')


class Buildbot(object):
    """If a master restart occurs, this object should be recreated as it caches
    some data.
    """
    auto_throttle = None

    def __init__(self, url):
        self.url = url + '/json/'
        self._builders = Builders(self)
        self._slaves = Slaves(self)
        self._data = None
        self.last_fetch = None

    @property
    def builders(self):
        return self._builders

    @property
    def slaves(self):
        return self._slaves

    @property
    def data(self):
        # TODO(maruel): Buildbot needs to expose version.
        if not self._data:
            self._data = self.read('project')
        return self._data

    def read(self, suburl):
        if self.auto_throttle:
            if self.last_fetch:
                delta = datetime.datetime.utcnow() - self.last_fetch
                remaining = (datetime.timedelta(seconds=self.auto_throttle) -
                        delta)
                if remaining > datetime.timedelta(seconds=0):
                    logging.debug('Sleeping for %ss' % remaining)
                    time.sleep(remaining.seconds)
            self.last_fetch = datetime.datetime.utcnow()
        url = self.url + suburl
        logging.info('read(%s)' % url)
        return json.load(urllib.urlopen(url))


def main(args=None):
    parser = optparse.OptionParser(
        usage='%prog <url> [options]',
        version=__version__,
        description=sys.modules[__name__].__doc__)
    parser.add_option('-v', '--verbose', action='count')
    parser.add_option(
        '-b', '--builder', dest='builders', action='append', default=[],
        help='Builders to filter on')
    parser.add_option(
        '-s', '--slave', dest='slaves', action='append', default=[],
        help='Slaves to filter on')
    parser.add_option(
        '-p', '--pending', action='store_true',
        help='Prints pending builds')
    parser.add_option(
            '--step',
            help='List all slaves that failed on that step on their last '
                 'build')
    parser.add_option(
            '-r', '--result', type='int', help='Build result to filter on')
    parser.add_option(
            '-n', '--no_cache', action='store_true',
            help='Don\'t load all builds at once')
    parser.add_option(
        '-t', '--throttle', type='int',
        help='Minimum delay to sleep between requests')
    options, args = parser.parse_args(args)
    if options.verbose:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.WARNING)
    if len(args) != 1:
        parser.error('Need to pass the root url of the buildbot')
    if options.pending and (options.slaves or options.step):
        parser.error(
            '--pending and --slave or --step cannot be used at the same time')
    if options.step and options.result is None:
        options.result = 2

    Buildbot.auto_throttle = options.throttle
    buildbot = Buildbot(args[0])
    if not options.builders:
        option.builders = buildbot.builders.keys
    for builder in options.builders:
        builder = buildbot.builders[builder]
        if options.pending:
            # TODO(maruel): A bit dry.
            pprint.pprint(builder.pendingBuilds)
            continue

        slaves = options.slaves
        if not slaves:
            slaves = builder.slaves.names
        else:
            # Only the subset of slaves connected to the builder.
            slaves = list(set(slaves).intersection(set(builder.slaves.names)))
            if not slaves:
                continue

        if not options.no_cache:
            # Unless you just want the last few builds, it's often faster to
            # fetch the whole thing at once, at the cost of a small hickup on
            # the buildbot.
            # TODO(maruel): Cache only N last builds or all builds since
            # datetime.
            builder.builds.cache()

        found = []

        for build in builder.builds:
            if not build.slave.name in slaves:
                continue
            if options.step:
                # For each slaves, finds which who failed at compile step on
                # their last build.
                if build.slave.name in found:
                    continue
                found.append(build.slave.name)
                if build.steps[options.step].result == 2:
                    print '%d on %s: result:%s blame:%s' % (
                        build.number, build.slave.name, build.result,
                        ', '.join(build.blamelist))
                    print build.slave.name
                if len(found) == len(slaves):
                    break
                logging.debug('%d remaining' % (len(slaves) - len(found)))
                continue

            if not options.result is None and build.result != options.result:
                continue
            print '%d on %s: result:%s blame:%s' % (
                build.number, build.slave.name, build.result,
                ', '.join(build.blamelist))
            for step in build.steps:
                if not step.result in (0, None):
                    print '%s: r=%s %s' % (
                        step.data['name'], step.result,
                        ', '.join(step.data['text']))
    return 0


if __name__ == '__main__':
    sys.exit(main())

# vim: ts=4:sw=4:tw=80:et:
