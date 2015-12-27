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

from __future__ import print_function

# TODO:
# * Properly name classes and methods.
# * Wrapped methods/classes should have appropriate docstrings.


class CompatibilityLevel:
    # Allow use of old worker API.
    allow = 0
    # Raise warnings about use of old worker API.
    warning = 1
    # Raise error when old worker API is tried to use
    error = 2


# Global compatibility level setting
_compatibility_level = None

DEFAULT_COMPATIBILITY_LEVEL = CompatibilityLevel.warning


def get_compatibility_level():
    """Returns current worker API compatibility level."""
    if _compatibility_level is None:
        return DEFAULT_COMPATIBILITY_LEVEL
    else:
        return _compatibility_level


def set_compatibility_level(level):
    """Sets worker API compatibility level."""
    global _compatibility_level
    # TODO: Is it may be changed several times?
    assert _compatibility_level is None, "API compatibility level already set"
    CL = CompatibilityLevel
    assert level in [CL.allow, CL.warning, CL.error]
    _compatibility_level = level


def _compat_name(new_name, pattern=None):
    """Returns old API ("slave") name for new name ("worker").

    >>> assert _compat_name("Worker") == "Slave"
    >>> assert _compat_name("SomeWorkerStuff") == "SomeSlaveStuff"
    >>> assert _compat_name("SomeWorker", pattern="BuildWorker") == \
        "SomeBuildSlave"

    Unfortunately "slave" -> "worker" renaming is not one-to-one relation,
    e.g.:
        "slave" -> "worker" (1)
        "Slave" -> "Worker" (2)
    but
        "buildslave" -> "worker" (3)
        "Buildslave" -> "Worker" (4)
        "BuildSlave" -> "Worker" (5)

    `pattern` parameter is used to specify which of (3), (4) or (5) case
    of renaming should be used. If `pattern` is not specified then rules
    (1) and (2) are applied.
    """

    allowed_patterns = {
        "BuildWorker": {"Worker": "BuildSlave"},
        "Buildworker": {"Worker": "Buildslave"},
        "buildworker": {"worker": "buildslave"},
    }

    if pattern is not None:
        compat_replacements = allowed_patterns[pattern]
    else:
        compat_replacements = {
            "worker": "slave",
            "Worker": "Slave",
        }

    compat_name = new_name
    assert "slave" not in compat_name.lower()
    assert "worker" in compat_name.lower()
    for new_word, old_word in compat_replacements.iteritems():
        compat_name = compat_name.replace(new_word, old_word)

    assert compat_name != new_name
    assert "slave" in compat_name.lower()
    assert "worker" not in compat_name.lower()

    return compat_name


def _on_old_name_usage(new_name, compat_name):
    """Hook that is ran when old API name is used.

    This hook will raise if old name usage is forbidden in the global settings.
    """
    message = (
        "Use of obsolete name '{compat_name}'. Use '{new_name}' "
        "instead. To disable this warning ...TODO".format(
            compat_name=compat_name, new_name=new_name))

    level = get_compatibility_level()
    if level == CompatibilityLevel.error:
        # TODO: Use proper exception class.
        raise RuntimeError(message)

    elif level == CompatibilityLevel.warning:
        # TODO: Use logging
        print("WARNING: {0}".format(message))
    else:
        assert level == CompatibilityLevel.allow


def define_old_worker_class_alias(scope, cls, pattern=None):
    """Add same class but with old API name.

    Useful for interfaces."""
    if get_compatibility_level() == CompatibilityLevel.error:
        # Don't define compatibility name.
        return

    compat_name = _compat_name(cls.__name__, pattern=pattern)

    assert compat_name not in scope
    scope[compat_name] = cls


def define_old_worker_class(scope, cls, pattern=None):
    """Define old-named class that inherits new names class.

    Useful for instantiable classes.
    """
    if get_compatibility_level() == CompatibilityLevel.error:
        # Don't define compatibility name.
        return

    compat_name = _compat_name(cls.__name__, pattern=pattern)

    def __new__(cls, *args, **kwargs):
        _on_old_name_usage(cls.__name__, compat_name)
        instance = cls.__new__(cls, *args, **kwargs)
        return instance

    compat_class = type(compat_name, (cls,), {"__new__": __new__})

    assert compat_name not in scope
    scope[compat_name] = compat_class


def define_old_worker_property(scope, name, pattern=None):
    """Define old-named property inside class."""
    compat_name = _compat_name(name, pattern=pattern)
    assert compat_name not in scope

    def get(self):
        _on_old_name_usage(name, compat_name)
        return getattr(self, name)

    scope[compat_name] = property(get)


def define_old_worker_method(scope, method, pattern=None):
    """Define old-named method inside class."""
    compat_name = _compat_name(method.__name__, pattern=pattern)
    assert compat_name not in scope

    def old_method(self, *args, **kwargs):
        _on_old_name_usage(method.__name__, compat_name)
        return method(self, *args, **kwargs)

    scope[compat_name] = old_method


class WorkerAPICompatMixin(object):
    """Mixin class for classes that have old-named worker attributes."""

    def __getattr__(self, name):
        if name not in self.__compat_attrs:
            raise AttributeError()

        new_name = self.__compat_attrs[name]

        # TODO: Log class name, operation type etc.
        _on_old_name_usage(new_name, name)

        return getattr(self, new_name)

    def __setattr__(self, name, value):
        if name in self.__compat_attrs:
            new_name = self.__compat_attrs[name]
            # TODO: Log class name, operation type etc.
            _on_old_name_usage(new_name, name)
            return setattr(self, new_name, value)
        else:
            self.__dict__[name] = value

    @property
    def __compat_attrs(self):
        # It's unreliable to initialize attributes in __init__() since
        # old-style classes are used and parent initializers are mostly
        # not called.
        if "_compat_attrs_mapping" not in self.__dict__:
            self.__dict__["_compat_attrs_mapping"] = {}
        return self._compat_attrs_mapping

    def _register_old_worker_attr(self, attr_name, pattern=None):
        """Define old-named attribute inside class instance."""
        compat_name = _compat_name(attr_name, pattern=pattern)
        assert compat_name not in self.__dict__
        assert compat_name not in self.__compat_attrs
        self.__compat_attrs[compat_name] = attr_name
