#!/usr/bin/env python
# Copyright (c) 2011 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file at
# http://src.chromium.org/viewvc/chrome/trunk/src/LICENSE
# This file is NOT under GPL.

"""Queries buildbot through the json interface.
"""

__author__ = 'maruel@chromium.org'
__version__ = '1.1'

import code
import datetime
import functools
import logging
import optparse
import time
import urllib
import urllib2
import sys

from find_json import json

import natsort

# These values are buildbot constants used for Build and BuildStep.
# This line was copied from master/buildbot/status/builder.py.
SUCCESS, WARNINGS, FAILURE, SKIPPED, EXCEPTION, RETRY = range(6)


## Generic node caching code.


class Node(object):
  """Root class for all nodes in the graph.

  Provides base functionality for any node in the graph, independent if it has
  children or not or if its content can be addressed through an url or needs to
  be fetched as part of another node.
  """
  # Mostly for help purposes. Used by __str__().
  children = []

  def __init__(self, parent, url):
    self.children = self.children[:]
    if url:
      self.children.append('url')
      url = url.rstrip('/')
    if parent is not None:
      self.children.append('parent')
    self.url = url
    self.parent = parent

  def __str__(self):
    return self.to_string()

  def __repr__(self):
    """Embeds key if present."""
    key = getattr(self, 'key', None)
    if key is not None:
      return '<%s key=%s>' % (self.__class__.__name__, key)
    return super(Node, self).__repr__()

  def to_string(self, maximum=100):
    out = ['%s:' % self.__class__.__name__]
    assert not 'children' in self.children

    def limit(txt):
      txt = str(txt)
      if maximum > 0:
        if len(txt) > maximum + 2:
          txt = txt[:maximum] + '...'
      return txt

    for k in self.children:
      if k == 'parent':
        # Avoid infinite recursion.
        continue
      value = '\n    '.join(limit(getattr(self, k)).splitlines())
      out.append('  %s: %s' % (k, value))
    return '\n'.join(out)

  def refresh(self):
    """Refreshes the data."""
    self.discard()
    return self.cache()

  def cache(self):  # pragma: no cover
    """Caches the data."""
    raise NotImplementedError()

  def discard(self):  # pragma: no cover
    """Discards cached data.

    Pretty much everything is temporary except completed Build.
    """
    raise NotImplementedError()


class AddressableBaseDataNode(Node):  # pylint: disable=W0223
  """A node that contains a dictionary of data that can be fetched with an url.

  The node is directly addressable. It also often can be fetched by the parent.
  """
  children = Node.children + ['data', 'cached_data']

  def __init__(self, parent, url, data):
    super(AddressableBaseDataNode, self).__init__(parent, url)
    self._data = data

  @property
  def cached_data(self):
    return self._data

  @property
  def data(self):
    self.cache()
    return self._data

  def cache(self):
    if self._data is None:
      self._data = self._readall()
      return True
    return False

  def discard(self):
    self._data = None

  def read(self, suburl):
    assert self.url, self.__class__.__name__
    url = self.url
    if suburl:
      url = '%s/%s' % (self.url, suburl)
    return self.parent.read(url)

  def _readall(self):
    return self.read('')


class AddressableDataNode(AddressableBaseDataNode):  # pylint: disable=W0223
  """Automatically encodes the url."""

  def __init__(self, parent, url, data):
    super(AddressableDataNode, self).__init__(parent, urllib.quote(url), data)


class NonAddressableDataNode(Node):  # pylint: disable=W0223
  """A node that cannot be addressed by an unique url.

  The data comes directly from the parent.
  """
  def __init__(self, parent, subkey):
    super(NonAddressableDataNode, self).__init__(parent, None)
    self.subkey = subkey

  @property
  def cached_data(self):
    if self.parent.cached_data is None:
      return None
    return self.parent.cached_data[self.subkey]

  @property
  def data(self):
    return self.parent.data[self.subkey]

  def cache(self):
    self.parent.cache()

  def discard(self):  # pragma: no cover
    """Avoid invalid state when parent recreate the object."""
    raise AttributeError('Call parent discard() instead')


class VirtualNodeList(Node):
  """Base class for every node that has children.

  Adds partial supports for keys and iterator functionality. 'key' can be a
  string or a int. Not to be used directly.
  """
  children = Node.children + ['keys', 'cached_children']

  def __init__(self, parent, url):
    super(VirtualNodeList, self).__init__(parent, url)
    # Keeps the keys independently when ordering is needed.
    self._is_cached = False
    self._has_keys_cached = False

  def __contains__(self, key):
    """Enables 'if i in obj:'."""
    return key in self.keys

  def __iter__(self):
    """Enables 'for i in obj:'. It returns children."""
    self.cache_keys()
    for key in self.keys:
      yield self[key]

  def __len__(self):
    """Enables 'len(obj)' to get the number of childs."""
    return len(self.keys)

  def discard(self):
    """Discards data.

    The default behavior is to not invalidate cached keys. The only place where
    keys need to be invalidated is with Builds.
    """
    self._is_cached = False
    self._has_keys_cached = False

  @property
  def cached_children(self):  # pragma: no cover
    """Returns an iterator over the children that are cached."""
    raise NotImplementedError()

  @property
  def keys(self):  # pragma: no cover
    """Returns the keys for every children."""
    raise NotImplementedError()

  def __getitem__(self, key):  # pragma: no cover
    """Returns a child, without fetching its data.

    The children could be invalid since no verification is done.
    """
    raise NotImplementedError()

  def cache(self):  # pragma: no cover
    """Cache all the children."""
    raise NotImplementedError()

  def cache_keys(self):  # pragma: no cover
    """Cache all children's keys."""
    raise NotImplementedError()


class NodeList(VirtualNodeList):  # pylint: disable=W0223
  """Adds a cache of the keys."""
  def __init__(self, parent, url):
    super(NodeList, self).__init__(parent, url)
    self._keys = []

  @property
  def keys(self):
    self.cache_keys()
    return self._keys


class NonAddressableNodeList(VirtualNodeList):  # pylint: disable=W0223
  """A node that contains children but retrieves all its data from its parent.

  I.e. there's no url to get directly this data.
  """
  # Child class object for children of this instance. For example, BuildSteps
  # has BuildStep children.
  _child_cls = None

  def __init__(self, parent, subkey):
    super(NonAddressableNodeList, self).__init__(parent, None)
    self.subkey = subkey
    assert (
        not isinstance(self._child_cls, NonAddressableDataNode) and
        issubclass(self._child_cls, NonAddressableDataNode)), (
        self._child_cls.__name__)

  @property
  def cached_children(self):
    if self.parent.cached_data is not None:
      for i in xrange(len(self.parent.cached_data[self.subkey])):
        yield self[i]

  @property
  def cached_data(self):
    if self.parent.cached_data is None:
      return None
    return self.parent.data.get(self.subkey, None)

  @property
  def data(self):
    return self.parent.data[self.subkey]

  @property
  def keys(self):  # pragma: no cover
    raise NotImplementedError()

  def cache(self):
    self.parent.cache()

  def cache_keys(self):
    self.parent.cache()

  def discard(self):  # pragma: no cover
    """Avoid infinite recursion by having the caller calls the parent's
    discard() explicitely.
    """
    raise AttributeError('Call parent discard() instead')

  def __iter__(self):
    """Enables 'for i in obj:'. It returns children."""
    if self.data:
      for i in xrange(len(self.data)):
        yield self[i]

  def __getitem__(self, key):
    """Doesn't cache the value, it's not needed.

    TODO(maruel): Cache?
    """
    if isinstance(key, int) and key < 0:
      key = len(self.data) + key
    # pylint: disable=E1102
    return self._child_cls(self, key)


class AddressableNodeList(NodeList):
  """A node that has children that can be addressed with an url."""

  # Child class object for children of this instance. For example, Builders has
  # Builder children and Builds has Build children.
  _child_cls = None

  def __init__(self, parent, url):
    super(AddressableNodeList, self).__init__(parent, url)
    self._cache = {}
    assert (
        not isinstance(self._child_cls, AddressableDataNode) and
        issubclass(self._child_cls, AddressableDataNode)), (
            self._child_cls.__name__)

  @property
  def cached_children(self):
    for item in self._cache.itervalues():
      if item.cached_data is not None:
        yield item

  def __getitem__(self, key):
    """Enables 'obj[i]'."""
    if self._has_keys_cached and not key in self._keys:
      raise KeyError(key)

    if not key in self._cache:
      # Create an empty object.
      self._create_obj(key, None)
    return self._cache[key]

  def cache(self):
    if not self._is_cached:
      data = self._readall()
      for key in sorted(data):
        self._create_obj(key, data[key])
      self._is_cached = True
      self._has_keys_cached = True

  def cache_partial(self, children):
    """Caches a partial number of children.

    This method is more efficient since it does a single request for all the
    children instead of one request per children.

    It only grab objects not already cached.
    """
    # pylint: disable=W0212
    if not self._is_cached:
      to_fetch = [
          child for child in children
          if not (child in self._cache and self._cache[child].cached_data)
      ]
      if to_fetch:
        # Similar to cache(). The only reason to sort is to simplify testing.
        params = '&'.join(
            'select=%s' % urllib.quote(str(v)) for v in sorted(to_fetch))
        data = self.read('?' + params)
        for key in sorted(data):
          self._create_obj(key, data[key])

  def cache_keys(self):
    """Implement to speed up enumeration. Defaults to call cache()."""
    if not self._has_keys_cached:
      self.cache()
      assert self._has_keys_cached

  def discard(self):
    """Discards temporary children."""
    super(AddressableNodeList, self).discard()
    for v in self._cache.itervalues():
      v.discard()

  def read(self, suburl):
    assert self.url, self.__class__.__name__
    url = self.url
    if suburl:
      url = '%s/%s' % (self.url, suburl)
    return self.parent.read(url)

  def _create_obj(self, key, data):
    """Creates an object of type self._child_cls."""
    # pylint: disable=E1102
    obj = self._child_cls(self, key, data)
    # obj.key and key may be different.
    # No need to overide cached data with None.
    if data is not None or obj.key not in self._cache:
      self._cache[obj.key] = obj
    if obj.key not in self._keys:
      self._keys.append(obj.key)

  def _readall(self):
    return self.read('')


class SubViewNodeList(VirtualNodeList):  # pylint: disable=W0223
  """A node that shows a subset of children that comes from another structure.

  The node is not addressable.

  E.g. the keys are retrieved from parent but the actual data comes from
  virtual_parent.
  """

  def __init__(self, parent, virtual_parent, subkey):
    super(SubViewNodeList, self).__init__(parent, None)
    self.subkey = subkey
    self.virtual_parent = virtual_parent
    assert isinstance(self.parent, AddressableDataNode)
    assert isinstance(self.virtual_parent, NodeList)

  @property
  def cached_children(self):
    if self.parent.cached_data is not None:
      for item in self.keys:
        if item in self.virtual_parent.keys:
          child = self[item]
          if child.cached_data is not None:
            yield child

  @property
  def keys(self):
    self.cache_keys()
    return self.parent.data.get(self.subkey, [])

  def cache(self):
    """Batch request for each child in a single read request."""
    if not self._is_cached:
      self.virtual_parent.cache_partial(self.keys)
      self._is_cached = True

  def cache_keys(self):
    if not self._has_keys_cached:
      self.parent.cache()
      self._has_keys_cached = True

  def discard(self):
    if self.parent.cached_data is not None:
      for child in self.virtual_parent.cached_children:
        if child.key in self.keys:
          child.discard()
      self.parent.discard()
    super(SubViewNodeList, self).discard()

  def __getitem__(self, key):
    """Makes sure the key is in our key but grab it from the virtual parent."""
    return self.virtual_parent[key]

  def __iter__(self):
    self.cache()
    return super(SubViewNodeList, self).__iter__()


###############################################################################
## Buildbot-specific code


class Slave(AddressableDataNode):
  children = AddressableDataNode.children + [
      'name', 'key', 'connected', 'version']

  def __init__(self, parent, name, data):
    super(Slave, self).__init__(parent, name, data)
    self.name = name
    self.key = self.name
    # TODO(maruel): Add SlaveBuilders and a 'builders' property.
    # TODO(maruel): Add a 'running_builds' property.

  @property
  def connected(self):
    return self.data['connected']

  @property
  def version(self):
    return self.data['version']


class Slaves(AddressableNodeList):
  _child_cls = Slave
  children = AddressableNodeList.children + ['names']

  def __init__(self, parent):
    super(Slaves, self).__init__(parent, 'slaves')
    self.children.append('names')

  @property
  def names(self):
    return self.keys


class BuilderSlaves(SubViewNodeList):
  """Similar to Slaves but only list slaves connected to a specific builder.
  """
  children = SubViewNodeList.children + ['names']

  def __init__(self, parent):
    super(BuilderSlaves, self).__init__(
        parent, parent.parent.parent.slaves, 'slaves')

  @property
  def names(self):
    return self.keys


class BuildStep(NonAddressableDataNode):
  children = NonAddressableDataNode.children + [
      'name', 'number', 'result', 'simplified_result']

  def __init__(self, parent, number):
    """It's already pre-loaded by definition since the data is retrieve via the
    Build object.
    """
    assert isinstance(number, int)
    super(BuildStep, self).__init__(parent, number)
    self.number = number

  @property
  def name(self):
    return self.data['name']

  @property
  def result(self):
    result = self.data.get('results')
    if result is None:
      # results may be 0, in that case with filter=1, the value won't be
      # present.
      if self.data.get('isFinished'):
        result = self.data.get('results', 0)
    while isinstance(result, list):
      result = result[0]
    return result

  @property
  def simplified_result(self):
    """Returns a simplified 3 state value, True, False or None."""
    result = self.result
    if result in (SUCCESS, WARNINGS, SKIPPED):
      return True
    elif result in (FAILURE, EXCEPTION):
      return False
    assert result is None
    return None


class BuildSteps(NonAddressableNodeList):
  """Duplicates keys to support lookup by both step number and step name."""
  children = NonAddressableNodeList.children + ['failed']
  _child_cls = BuildStep

  def __init__(self, parent):
    """It's already pre-loaded by definition since the data is retrieve via the
    Build object.
    """
    super(BuildSteps, self).__init__(parent, 'steps')

  @property
  def keys(self):
    """Returns the indexes of the steps.

    It could return the build names but then it wouldn't be ordered."""
    return range(len(self.data or []))

  @property
  def failed(self):
    """Shortcuts that lists the step names of steps that failed."""
    return [step.name for step in self if step.simplified_result is False]

  def __getitem__(self, key):
    """Accept step name in addition to index number."""
    if isinstance(key, basestring):
      # It's a string, try to find the corresponding index.
      for i, step in enumerate(self.data):
        if step['name'] == key:
          key = i
          break
      else:
        raise KeyError(key)
    return super(BuildSteps, self).__getitem__(key)


class Build(AddressableDataNode):
  children = AddressableDataNode.children + [
      'key', 'number', 'steps', 'blame', 'reason', 'revision', 'result',
      'simplified_result', 'slave', 'properties']

  def __init__(self, parent, key, data):
    super(Build, self).__init__(parent, str(key), data)
    self.number = int(key)
    self.key = self.number
    self.steps = BuildSteps(self)

  @property
  def blame(self):
    return self.data.get('blame')

  @property
  def builder(self):
    """Returns the Builder object.

    Goes up the hierarchy to find the Buildbot.builders[builder] instance.
    """
    return self.parent.parent.parent.parent.builders[self.data['builderName']]

  @property
  def eta(self):
    return self.data.get('eta', 0)

  @property
  def properties(self):
    return self.data['properties']

  @property
  def reason(self):
    return self.data.get('reason')

  @property
  def result(self):
    result = self.data.get('results')
    while isinstance(result, list):
      result = result[0]
    if result is None and self.steps:
      # results may be 0, in that case with filter=1, the value won't be
      # present.
      result = self.steps[-1].result
    return result

  @property
  def revision(self):
    return self.data['sourceStamp'].get('revision')

  @property
  def simplified_result(self):
    """Returns a simplified 3 state value, True, False or None."""
    result = self.result
    if result in (SUCCESS, WARNINGS, SKIPPED):
      return True
    elif result in (FAILURE, EXCEPTION):
      return False
    assert result is None
    return None

  @property
  def slave(self):
    """Returns the Slave object.

    Goes up the hierarchy to find the Buildbot.slaves[slave] instance.
    """
    return self.parent.parent.parent.parent.slaves[self.data['slave']]

  def discard(self):
    """Completed Build isn't discarded."""
    if self._data and self.result is None:
      assert not self.steps or not self.steps[-1].data.get('isFinished')
      self._data = None


class CurrentBuilds(SubViewNodeList):
  """Lists of the current builds."""
  def __init__(self, parent):
    super(CurrentBuilds, self).__init__(
        parent, parent.builds, 'currentBuilds')


class PendingBuilds(AddressableDataNode):
  def __init__(self, parent):
    super(PendingBuilds, self).__init__(parent, 'pendingBuilds', None)


class Builds(AddressableNodeList):
  """Supports iteration.

  Recommends using .cache() to speed up if a significant number of builds are
  iterated over.
  """
  _child_cls = Build

  def __init__(self, parent):
    super(Builds, self).__init__(parent, 'builds')

  def __getitem__(self, key):
    """Adds supports for negative reference.

    e.g. -1 is the last build, -2 is the previous build before the last one.
    """
    key = int(key)
    if key < 0:
      # Convert negative to positive build number.
      self.cache_keys()
      key = self._keys[key]
    return super(Builds, self).__getitem__(key)

  def __iter__(self):
    """Returns in reversed order.

    The most recent build is returned first and then in reverse chronological
    order, up to the oldest cached build by the server. Older builds can be
    accessed but will trigger significantly more I/O so they are not included by
    default in the iteration.
    """
    self.cache()
    return reversed(self._cache.values())

  def cache_keys(self):
    """Grabs the keys (build numbers) from the builder."""
    if not self._has_keys_cached:
      for i in self.parent.data['cachedBuilds']:
        i = int(i)
        self._cache.setdefault(i, Build(self, i, None))
        if i not in self._keys:
          self._keys.append(i)
      self._has_keys_cached = True

  def discard(self):
    super(Builds, self).discard()
    # Can't keep keys.
    self._has_keys_cached = False

  def _readall(self):
    return self.read('_all')


class Builder(AddressableDataNode):
  children = AddressableDataNode.children + [
      'name', 'key', 'builds', 'slaves', 'pending_builds', 'current_builds']

  def __init__(self, parent, name, data):
    super(Builder, self).__init__(parent, name, data)
    self.name = name
    self.key = name
    self.builds = Builds(self)
    self.slaves = BuilderSlaves(self)
    self.current_builds = CurrentBuilds(self)
    self.pending_builds = PendingBuilds(self)

  def discard(self):
    super(Builder, self).discard()
    self.builds.discard()
    self.slaves.discard()
    self.current_builds.discard()


class Builders(AddressableNodeList):
  """Root list of builders."""
  _child_cls = Builder

  def __init__(self, parent):
    super(Builders, self).__init__(parent, 'builders')


class Buildbot(AddressableBaseDataNode):
  """If a master restart occurs, this object should be recreated as it caches
  data.
  """
  # Throttle fetches to not kill the server.
  auto_throttle = None
  children = AddressableDataNode.children + [
      'slaves', 'builders', 'last_fetch']

  def __init__(self, url):
    super(Buildbot, self).__init__(None, url.rstrip('/') + '/json', None)
    self._builders = Builders(self)
    self._slaves = Slaves(self)
    self.last_fetch = None

  @property
  def builders(self):
    return self._builders

  @property
  def slaves(self):
    return self._slaves

  def discard(self):
    """Discards information about Builders and Slaves."""
    super(Buildbot, self).discard()
    self._builders.discard()
    self._slaves.discard()

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
    url = '%s/%s' % (self.url, suburl)
    if '?' in url:
      url += '&filter=1'
    else:
      url += '?filter=1'
    logging.info('read(%s)' % suburl)
    channel = urllib.urlopen(url)
    try:
      return json.load(channel)
    except ValueError, e:
      if '<head><title>404 - No Such Resource</title></head>' in e.doc:
        raise urllib2.HTTPError(
            url, 404, '%s:\n%s' % (url, e.doc), channel.headers, None)
      raise

  def _readall(self):
    return self.read('project')


###############################################################################
## Controller code


def usage(more):
  def hook(fn):
    fn.func_usage_more = more
    return fn
  return hook


def need_buildbot(fn):
  """Post-parse args to create a buildbot object."""
  @functools.wraps(fn)
  def hook(parser, args, *extra_args, **kwargs):
    old_parse_args = parser.parse_args
    def new_parse_args(args):
      options, args = old_parse_args(args)
      if len(args) < 1:
        parser.error('Need to pass the root url of the buildbot')
      url = args.pop(0)
      if not url.startswith('http'):
        url = 'http://' + url
      buildbot = Buildbot(url)
      buildbot.auto_throttle = options.throttle
      return options, args, buildbot
    parser.parse_args = new_parse_args
    # Call the original function with the modified parser.
    return fn(parser, args, *extra_args, **kwargs)

  hook.func_usage_more = '[options] <url>'
  return hook


@need_buildbot
def CMDpending(parser, args):
  """Lists pending jobs."""
  parser.add_option(
    '-b', '--builder', dest='builders', action='append', default=[],
    help='Builders to filter on')
  options, args, buildbot = parser.parse_args(args)
  if args:
    parser.error('Unrecognized parameters: %s' % ' '.join(args))
  if not options.builders:
    options.builders = buildbot.builders.keys
  for builder in options.builders:
    builder = buildbot.builders[builder]
    pending_builds = builder.data.get('pendingBuilds', 0)
    if not pending_builds:
      continue
    print 'Builder %s: %d' % (builder.name, pending_builds)
    if not options.quiet:
      for pending in builder.pending_builds.data:
        if 'revision' in pending['source']:
          print '  revision: %s' % pending['source']['revision']
        for change in pending['source']['changes']:
          print '  change:'
          print '    comment: %r' % change['comments'][:50]
          print '    who:     %s' % change['who']
  return 0


@usage('[options] <url> [commands] ...')
@need_buildbot
def CMDrun(parser, args):
  """Runs commands passed as parameters.

  When passing commands on the command line, each command will be run as if it
  was on its own line.
  """
  parser.add_option('-f', '--file', help='Read script from file')
  parser.add_option(
      '-i', dest='use_stdin', action='store_true', help='Read script on stdin')
  # Variable 'buildbot' is not used directly.
  # pylint: disable=W0612
  options, args, buildbot = parser.parse_args(args)
  if (bool(args) + bool(options.use_stdin) + bool(options.file)) != 1:
    parser.error('Need to pass only one of: <commands>, -f <file> or -i')
  if options.use_stdin:
    cmds = sys.stdin.read()
  elif options.file:
    cmds = open(options.file).read()
  else:
    cmds = '\n'.join(args)
  compiled = compile(cmds, '<cmd line>', 'exec')
  eval(compiled, globals(), locals())
  return 0


@need_buildbot
def CMDinteractive(parser, args):
  """Runs an interactive shell to run queries."""
  _, args, buildbot = parser.parse_args(args)
  if args:
    parser.error('Unrecognized parameters: %s' % ' '.join(args))
  prompt = (
      'Buildbot interactive console for "%s".\n'
      'Hint: Start with typing: \'buildbot.children\' or '
      '\'print str(buildbot)\' to explore.') % buildbot.url[:-len('/json')]
  local_vars = {
      'buildbot': buildbot,
      'b': buildbot,
      'natsort': natsort,
  }
  code.interact(prompt, None, local_vars)


@need_buildbot
def CMDidle(parser, args):
  """Lists idle slaves."""
  return find_idle_busy_slaves(parser, args, True)


@need_buildbot
def CMDbusy(parser, args):
  """Lists idle slaves."""
  return find_idle_busy_slaves(parser, args, False)


def find_idle_busy_slaves(parser, args, show_idle):
  parser.add_option(
    '-b', '--builder', dest='builders', action='append', default=[],
    help='Builders to filter on')
  parser.add_option(
    '-s', '--slave', dest='slaves', action='append', default=[],
    help='Slaves to filter on')
  options, args, buildbot = parser.parse_args(args)
  if args:
    parser.error('Unrecognized parameters: %s' % ' '.join(args))
  if not options.builders:
    options.builders = buildbot.builders.keys
  for builder in options.builders:
    builder = buildbot.builders[builder]
    if options.slaves:
      # Only the subset of slaves connected to the builder.
      slaves = list(set(options.slaves).intersection(set(builder.slaves.names)))
      if not slaves:
        continue
    else:
      slaves = builder.slaves.names
    busy_slaves = [build.slave.name for build in builder.current_builds]
    if show_idle:
      slaves = natsort.natsorted(set(slaves) - set(busy_slaves))
    else:
      slaves = natsort.natsorted(set(slaves) & set(busy_slaves))
    if options.quiet:
      for slave in slaves:
        print slave
    else:
      if slaves:
        print 'Builder %s: %s' % (builder.name, ', '.join(slaves))
  return 0


def last_failure(buildbot, builders=None, slaves=None, steps=None,
    result=FAILURE, no_cache=False):
  """Generator returning Build object that were the last failure with the
  specific filters.
  """
  builders = builders or buildbot.builders.keys
  for builder in builders:
    builder = buildbot.builders[builder]
    if slaves:
      # Only the subset of slaves connected to the builder.
      builder_slaves = list(set(slaves).intersection(set(builder.slaves.names)))
      if not builder_slaves:
        continue
    else:
      builder_slaves = builder.slaves.names

    if not no_cache and len(builder.slaves) > 2:
      # Unless you just want the last few builds, it's often faster to
      # fetch the whole thing at once, at the cost of a small hickup on
      # the buildbot.
      # TODO(maruel): Cache only N last builds or all builds since
      # datetime.
      builder.builds.cache()

    found = []
    for build in builder.builds:
      if build.slave.name not in builder_slaves or  build.slave.name in found:
        continue
      found.append(build.slave.name)
      if steps:
        if any(build.steps[step].result == result for step in steps):
          yield build
      elif result is None or build.result == result:
        yield build
      if len(found) == len(slaves):
        # Found all the slaves, quit.
        break


@need_buildbot
def CMDlast_failure(parser, args):
  """Lists all slaves that failed on that step on their last build.

  Example: to find all slaves where their last build was a compile failure,
  run with --step compile"""
  parser.add_option(
    '-S', '--step', dest='steps', action='append', default=[],
    help='List all slaves that failed on that step on their last build')
  parser.add_option(
    '-r', '--result', type='int', default=FAILURE,
    help='Build result to filter on')
  parser.add_option(
    '-b', '--builder', dest='builders', action='append', default=[],
    help='Builders to filter on')
  parser.add_option(
    '-s', '--slave', dest='slaves', action='append', default=[],
    help='Slaves to filter on')
  parser.add_option(
    '-n', '--no_cache', action='store_true',
    help='Don\'t load all builds at once')
  options, args, buildbot = parser.parse_args(args)
  if args:
    parser.error('Unrecognized parameters: %s' % ' '.join(args))
  if options.steps and options.result is None:
    options.result = 2
  print_builders = not options.quiet and len(options.builders) != 1
  last_builder = None
  for build in last_failure(buildbot, builders=options.builders,
      slaves=options.slaves, steps=options.steps, result=options.result,
      no_cache=options.no_cache):

    if print_builders and last_builder != build.builder:
      print build.builder.name
      last_builder = build.builder

    if options.quiet:
      if options.slaves:
        print '%s: %s' % (build.builder.name, build.slave.name)
      else:
        print build.slave.name
    else:
      out = '%d on %s: result:%s blame:%s' % (
        build.number, build.slave.name, build.result,
        ', '.join(build.blame))
      if print_builders:
        out = '  ' + out
      print out

      if len(options.steps) != 1:
        for step in build.steps:
          if step.result not in (0, None):
            out = '  %s: r=%s %s' % (
                step.data['name'], step.result,
                ', '.join(step.data['text'])[:40])
            if print_builders:
              out = '  ' + out
            print out
  return 0


@need_buildbot
def CMDcurrent(parser, args):
  """Lists current jobs."""
  parser.add_option(
    '-b', '--builder', dest='builders', action='append', default=[],
    help='Builders to filter on')
  options, args, buildbot = parser.parse_args(args)
  if args:
    parser.error('Unrecognized parameters: %s' % ' '.join(args))
  if not options.builders:
    options.builders = buildbot.builders.keys
  for builder in options.builders:
    builder = buildbot.builders[builder]
    if not options.quiet and builder.current_builds:
      print builder.name
    for build in builder.current_builds:
      if options.quiet:
        print build.slave.name
      else:
        out = '%d: slave=%s' % (build.number, build.slave.name)
        if build.eta:
          out += '  eta=%.0f' % build.eta
        if build.blame:
          out += '  blame=' + ', '.join(build.blame)
        print out

  return 0


def gen_parser():
  """Returns an OptionParser instance with default options.

  It should be then processed with gen_usage() before being used.
  """
  parser = optparse.OptionParser(
    version=__version__)
  # Remove description formatting
  parser.format_description = lambda x: parser.description
  # Add common parsing.
  old_parser_args = parser.parse_args
  def Parse(*args, **kwargs):
    options, args = old_parser_args(*args, **kwargs)
    if options.verbose >= 2:
      logging.basicConfig(level=logging.DEBUG)
    elif options.verbose:
      logging.basicConfig(level=logging.INFO)
    else:
      logging.basicConfig(level=logging.WARNING)
    return options, args
  parser.parse_args = Parse

  parser.add_option(
    '-v', '--verbose', action='count',
    help='Use multiple times to increase logging leve')
  parser.add_option(
    '-q', '--quiet', action='store_true',
    help='Reduces the output to be parsed by scripts, independent of -v')
  parser.add_option(
    '--throttle', type='float',
    help='Minimum delay to sleep between requests')
  return parser


###############################################################################
## Generic subcommand handling code


def Command(name):
  return getattr(sys.modules[__name__], 'CMD' + name, None)


@usage('<command>')
def CMDhelp(parser, args):
  """Print list of commands or use 'help <command>'."""
  _, args = parser.parse_args(args)
  if len(args) == 1:
    return main(args + ['--help'])
  parser.print_help()
  return 0


def gen_usage(parser, command):
  """Modifies an OptionParser object with the command's documentation.

  The documentation is taken from the function's docstring.
  """
  obj = Command(command)
  more = getattr(obj, 'func_usage_more')
  # OptParser.description prefer nicely non-formatted strings.
  parser.description = obj.__doc__ + '\n'
  parser.set_usage('usage: %%prog %s %s' % (command, more))


def main(args=None):
  # Do it late so all commands are listed.
  # pylint: disable=E1101
  CMDhelp.__doc__ += '\n\nCommands are:\n' + '\n'.join(
      '  %-12s %s' % (fn[3:], Command(fn[3:]).__doc__.split('\n', 1)[0])
      for fn in dir(sys.modules[__name__]) if fn.startswith('CMD'))

  parser = gen_parser()
  if args is None:
    args = sys.argv[1:]
  if args:
    command = Command(args[0])
    if command:
      # "fix" the usage and the description now that we know the subcommand.
      gen_usage(parser, args[0])
      return command(parser, args[1:])

  # Not a known command. Default to help.
  gen_usage(parser, 'help')
  return CMDhelp(parser, args)


if __name__ == '__main__':
  sys.exit(main())
