# This file is part of Buildbot.  Buildbot is free software: you can
# redistribute it and/or modify it under the terms of the GNU General Public
# License as published by the Free Software Foundation, version 2.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more
# details.
#
# You should have received a copy of the GNU General Public License along with
# this program; if not, write to the Free Software Foundation, Inc., 51
# Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#
# Copyright Buildbot Team Members
#
# pylint: disable=C0111
from future.utils import iteritems
from future.utils import itervalues

from pkg_resources import iter_entry_points
from warnings import warn

from zope.interface import Invalid
from zope.interface.verify import verifyClass

from buildbot.errors import PluginDBError
from buildbot.interfaces import IPlugin


# Base namespace for Buildbot specific plugins
_NAMESPACE_BASE = 'buildbot'


class _PluginEntry(object):
    def __init__(self, group, entry, loader):
        super(_PluginEntry, self).__init__()

        self._group = group
        self._entry = entry
        self._value = None
        self._loader = loader

    def load(self):
        if self._value is None:
            self._value = self._loader(self._entry)

    @property
    def group(self):
        return self._group

    @property
    def name(self):
        return self._entry.name

    @property
    def info(self):
        dist = self._entry.dist
        return (dist.project_name, dist.version)

    @property
    def value(self):
        self.load()
        return self._value

    def __ne__(self, other):
        return self.info != other.info


class _NSNode(object):
    def __init__(self):
        super(_NSNode, self).__init__()

        self._children = dict()

    def load(self):
        for child in itervalues(self._children):
            child.load()

    def add(self, name, entry):
        assert isinstance(name, basestring) and isinstance(entry, _PluginEntry)
        self._add(name, entry)

    def _add(self, name, entry):
        path = name.split('.', 1)
        key = path.pop(0)
        is_leaf = not path
        child = self._children.get(key)

        if is_leaf:
            if child is not None:
                assert isinstance(child, _PluginEntry)
                if child != entry:
                    raise PluginDBError('Duplicate entry point for "%s:%s".\n'
                                        '  Previous definition %s\n'
                                        '  This definition %s' %
                                        (child.group, child.name, child.info,
                                         entry.info))
            else:
                self._children[key] = entry
        else:
            if child is None:
                child = _NSNode()
            assert isinstance(child, _NSNode)
            child._add(path[0], entry)
            self._children[key] = child

    def __getattr__(self, name):
        child = self._children.get(name)
        if child is None:
            raise PluginDBError('Unknown component name: %s' % name)

        if isinstance(child, _PluginEntry):
            return child.value
        else:
            return child

    def info(self, name):
        assert isinstance(name, basestring)

        return self._get(name).info

    def get(self, name):
        assert isinstance(name, basestring)

        return self._get(name).value

    def _get(self, name):
        path = name.split('.', 1)
        key = path.pop(0)
        is_leaf = not path
        child = self._children.get(key)

        if isinstance(child, _PluginEntry):
            if not is_leaf:
                raise PluginDBError('Excessive namespace specification: %s' %
                                    path[0])
            return child
        elif child is None:
            raise PluginDBError('Unknown component name: %s' % name)
        else:
            return child._get(path[0])

    def _info_all(self):
        result = []
        for key, child in iteritems(self._children):
            if isinstance(child, _PluginEntry):
                result.append((key, child.info))
            else:
                result.extend([
                    ('%s.%s' % (key, name), value)
                    for name, value in iteritems(child.info_all())
                ])
        return result

    def info_all(self):
        return dict(self._info_all())


class _Plugins(object):
    """
    represent plugins within a namespace
    """

    def __init__(self, namespace, interface=None, check_extras=True,
                 deprecations=None, warning=DeprecationWarning):
        super(_Plugins, self).__init__()

        if interface is not None:
            assert interface.isOrExtends(IPlugin)

        self._namespace = namespace
        self._group = '%s.%s' % (_NAMESPACE_BASE, namespace)

        self._interface = interface
        self._check_extras = check_extras

        self._real_tree = None

        if deprecations is None:
            deprecations = dict()

        self._deprecations = dict(deprecations)
        self._warning = warning

    def _load_entry(self, entry):
        # pylint: disable=W0703
        if self._check_extras:
            try:
                entry.require()
            except Exception as err:
                raise PluginDBError('Requirements are not satisfied '
                                    'for %s:%s: %s' % (self._group,
                                                       entry.name,
                                                       str(err)))
        try:
            result = entry.load()
        except Exception as err:
            raise PluginDBError('Unable to load %s:%s: %s' %
                                (self._group, entry.name, str(err)))
        if self._interface:
            try:
                verifyClass(self._interface, result)
            except Invalid as err:
                raise PluginDBError('Plugin %s:%s does not implement %s: %s' %
                                    (self._group, entry.name,
                                     self._interface.__name__, str(err)))
        return result

    @property
    def _tree(self):
        if self._real_tree is None:
            self._real_tree = _NSNode()
            for entry in iter_entry_points(self._group):
                self._real_tree.add(entry.name,
                                    _PluginEntry(self._group, entry,
                                                 self._load_entry))
        return self._real_tree

    def load(self):
        self._tree.load()

    def info_all(self):
        return self._tree.info_all()

    @property
    def namespace(self):
        return self._namespace

    @property
    def names(self):
        # Expensive operation
        return list(self.info_all())

    def info(self, name):
        """
        get information about a particular plugin if known in this namespace
        """
        return self._tree.info(name)

    def __contains__(self, name):
        """
        check if the given name is available as a plugin
        """
        try:
            return not isinstance(self._tree.get(name), _NSNode)
        except PluginDBError:
            return False

    def get(self, name):
        """
        get an instance of the plugin with the given name
        """
        if name in self._deprecations:
            new_name = self._deprecations[name]

            warn('use of {group}.{name} plugin is deprecated; '
                 'use {group}.{new_name} instead'.format(
                     group=self._group,
                     name=name,
                     new_name=new_name),
                 self._warning)

            name = new_name

        return self._tree.get(name)

    def __getattr__(self, name):
        try:
            return getattr(self._tree, name)
        except PluginDBError as err:
            raise AttributeError(str(err))


class _DeprecatedPlugins(object):
    """
    represent plugins from a deprecated namespace
    """

    def __init__(self, namespace, target, mapping, warning=DeprecationWarning):
        super(_DeprecatedPlugins, self).__init__()

        assert isinstance(target, _Plugins)
        assert issubclass(warning, (DeprecationWarning, Warning)), \
                          'Oopsy: %r' % (warning,)

        self._namespace = namespace
        self._target = target
        self._mapping = dict(mapping)
        self._warning = warning

    def __contains__(self, name):
        warn('"buildbot.plugins.{namespace}" plugins namespace is deprecated; '
             'use "buildbot.plugins.{target}" instead '.format(
                 namespace=self._namespace,
                 target=self._target.namespace),
             self._warning)
        return _Plugins.__contains__(self, name)

    def get(self, name):
        warn('"buildbot.plugins.{namespace}" plugins namespace is deprecated, '
             'use "buildbot.plugins.{target}" instead (you requested "{name}" '
             'via "buildbot.plugins.{namespace}" namespace).'.format(
                 name=name,
                 namespace=self._namespace,
                 target=self._target.namespace),
             self._warning)

        return _Plugins.get(self, name)

    def __getattr__(self, name):
        warn('"buildbot.plugins.buildslave" plugins namespace is deprecated; '
             'use "buildbot.plugins.worker" instead '
             '(you accessed "buildslave.{0}" name).'.format(name),
             self._warning)

        return _Plugins.__getattr__(self, name)


class _PluginDB(object):
    """
    Plugin infrastructure support for Buildbot
    """

    def __init__(self):
        super(_PluginDB, self).__init__()

        self._namespaces = dict()

    def add_transition_namespace(self, namespace, namespace_to, mapping,
                                 exception=DeprecationWarning):
        """
        register given namespace in global database of plugins
        """
        tempo = self._namespaces.get(namespace)

        if tempo is None:
            target_ns = self._namespaces.get(namespace_to)

            assert target_ns is not None, \
                'Namespace "%s" must be defined' % (namespace_to,)

            tempo = _DeprecatedPlugins(namespace, target_ns, mapping, exception)
            self._namespaces[namespace] = tempo

        return tempo

    def add_namespace(self, namespace, interface=None, check_extras=True,
                      load_now=False, deprecations=None,
                      warning=DeprecationWarning):
        """
        register given namespace in global database of plugins

        in case it's already registered, return the registration
        """
        tempo = self._namespaces.get(namespace)

        if tempo is None:
            tempo = _Plugins(namespace, interface, check_extras,
                             deprecations=deprecations, warning=warning)

            self._namespaces[namespace] = tempo

        if load_now:
            tempo.load()

        return tempo

    @property
    def namespaces(self):
        """
        get a list of registered namespaces
        """
        return list(self._namespaces)

    def info(self):
        """
        get information about all plugins in registered namespaces
        """
        result = dict()
        for name, namespace in iteritems(self._namespaces):
            result[name] = namespace.info_all()
        return result


_DB = _PluginDB()


def namespaces():
    """
    provide information about known namespaces
    """
    return _DB.namespaces


def info():
    """
    provide information about all known plugins

    format of the output:

    {<namespace>, {
        {<plugin-name>: (<package-name>, <package-version),
         ...},
        ...
    }
    """
    return _DB.info()


def get_plugins(namespace, interface=None, check_extras=True, load_now=False,
                deprecations=None, warning=DeprecationWarning):
    """
    get a direct interface to _Plugins
    """
    return _DB.add_namespace(namespace, interface, check_extras, load_now,
                             deprecations, warning)


def handle_transition_plugins(namespace, namespace_to, mapping,
                              warning=DeprecationWarning):
    """
    register a proxy for a deprecated namespace
    """
    return _DB.add_transition_namespace(namespace, namespace_to, mapping,
                                        warning)
