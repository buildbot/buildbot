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

"""
Utility functions to support transition from "slave"-named API to
"worker"-named.

Use of old API generates Python warning which may be logged, ignored or treated
as an error using Python builtin warnings API.
"""

import functools
import warnings

__all__ = (
    "DeprecatedWorkerNameWarning", "define_old_worker_class_alias",
    "define_old_worker_class", "define_old_worker_property",
    "define_old_worker_method", "define_old_worker_func",
    "WorkerAPICompatMixin",
    "deprecated_worker_class", "deprecated_name",
)

# TODO:
# * Properly name classes and methods.
# * Aliases are defined even they usage will be forbidden later.
# * function wrapper is almost identical to method wrapper (they are both
#   just functions from Python side of view), probably method wrapper should
#   be dropped.
# * At some point old API support will be dropped and this module will be
#   removed. It's good to think now how this can be gracefully done later.
#   For example, if I explicitly configure warnings in buildbot.tac template
#   now, later generated from such template buildbot.tac files will break.
# * Perhaps remove "pattern" from deprecated_name() and always use "name"?


def deprecated_name(new_name, pattern=None):
    """Returns old API ("slave") name for new name ("worker").

    >>> assert deprecated_name("Worker") == "Slave"
    >>> assert deprecated_name("SomeWorkerStuff") == "SomeSlaveStuff"
    >>> assert deprecated_name("SomeWorker", pattern="BuildWorker") == \
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


# DeprecationWarning or PendingDeprecationWarning may be used as
# the base class, but by default deprecation warnings are disabled in Python,
# so by default old-API usage warnings will be ignored - this is not what
# we want.
class DeprecatedWorkerAPIWarning(Warning):
    """Base class for deprecated API warnings."""


class DeprecatedWorkerNameWarning(DeprecatedWorkerAPIWarning):
    """Warning class for use of deprecated classes, functions, methods
    and attributes.
    """


# Separate warnings about deprecated modules from other deprecated
# identifiers.  Deprecated modules are loaded only once and it's hard to
# predict in tests exact places where warning should be issued (in contrast
# warnings about other identifiers will be issued every usage).
class DeprecatedWorkerModuleWarning(DeprecatedWorkerAPIWarning):
    """Warning class for use of deprecated modules."""


# TODO: make stacklevel relative to caller function
def on_deprecated_name_usage(message, stacklevel=None, filename=None,
                             lineno=None):
    """Hook that is ran when old API name is used."""

    if filename is None:
        if stacklevel is None:
            # Warning will refer to the caller of the caller of this function.
            stacklevel = 3

        warnings.warn(DeprecatedWorkerNameWarning(message), None, stacklevel)

    else:
        assert stacklevel is None

        if lineno is None:
            lineno = 0

        warnings.warn_explicit(
            DeprecatedWorkerNameWarning(message),
            DeprecatedWorkerNameWarning,
            filename, lineno)


def on_deprecated_module_usage(message, stacklevel=None):
    """Hook that is ran when old API module is used."""

    if stacklevel is None:
        # Warning will refer to the caller of the caller of this function.
        stacklevel = 3

    warnings.warn(DeprecatedWorkerModuleWarning(message), None, stacklevel)


def define_old_worker_class_alias(scope, cls, pattern=None):
    """Add same class but with old API name.

    Useful for interfaces."""

    compat_name = deprecated_name(cls.__name__, pattern=pattern)

    scope[compat_name] = cls


def deprecated_worker_class(cls, pattern=None, name=None):
    assert issubclass(cls, object)

    if name is not None:
        assert pattern is None
        compat_name = name
    else:
        compat_name = deprecated_name(cls.__name__, pattern=pattern)

    def __new__(instance_cls, *args, **kwargs):
        on_deprecated_name_usage(
            "'{old}' class is deprecated, use '{new}' instead.".format(
                new=cls.__name__, old=compat_name))
        if cls.__new__ is object.__new__:
            # object.__new__() doesn't accept arguments.
            instance = cls.__new__(instance_cls)
        else:
            # Class has overloaded __new__(), pass arguments to it.
            instance = cls.__new__(instance_cls, *args, **kwargs)

        return instance

    compat_class = type(compat_name, (cls,), {
        "__new__": __new__,
        "__module__": cls.__module__,
        "__doc__": cls.__doc__,
        })

    return compat_class


def define_old_worker_class(scope, cls, pattern=None, name=None):
    """Define old-named class that inherits new names class.

    Useful for instantiable classes.
    """

    compat_class = deprecated_worker_class(cls, pattern=pattern, name=name)
    scope[compat_class.__name__] = compat_class


def define_old_worker_property(scope, name, pattern=None):
    """Define old-named property inside class."""
    compat_name = deprecated_name(name, pattern=pattern)
    assert compat_name not in scope

    def get(self):
        on_deprecated_name_usage(
            "'{old}' attribute is deprecated, use '{new}' instead.".format(
                new=name, old=compat_name))
        return getattr(self, name)

    scope[compat_name] = property(get)


def define_old_worker_method(scope, method, pattern=None, name=None):
    """Define old-named method inside class."""
    method_name = method.__name__

    if name is not None:
        assert pattern is None
        compat_name = name
    else:
        compat_name = deprecated_name(method_name, pattern=pattern)

    assert compat_name not in scope

    def old_method(self, *args, **kwargs):
        on_deprecated_name_usage(
            "'{old}' method is deprecated, use '{new}' instead.".format(
                new=method_name, old=compat_name))
        return getattr(self, method_name)(*args, **kwargs)

    functools.update_wrapper(old_method, method)

    scope[compat_name] = old_method


def define_old_worker_func(scope, func, pattern=None):
    """Define old-named function."""
    compat_name = deprecated_name(func.__name__, pattern=pattern)

    def old_func(*args, **kwargs):
        on_deprecated_name_usage(
            "'{old}' function is deprecated, use '{new}' instead.".format(
                new=func.__name__, old=compat_name))
        return func(*args, **kwargs)

    functools.update_wrapper(old_func, func)

    scope[compat_name] = old_func


class WorkerAPICompatMixin(object):
    """Mixin class for classes that have old-named worker attributes."""

    def __getattr__(self, name):
        if name not in self.__compat_attrs:
            raise AttributeError(
                "'{class_name}' object has no attribute '{attr_name}'".format(
                    class_name=self.__class__.__name__,
                    attr_name=name))

        new_name = self.__compat_attrs[name]

        # TODO: Log class name, operation type etc.
        on_deprecated_name_usage(
            "'{old}' attribute is deprecated, use '{new}' instead.".format(
                new=new_name, old=name))

        return getattr(self, new_name)

    def __setattr__(self, name, value):
        if name in self.__compat_attrs:
            new_name = self.__compat_attrs[name]
            # TODO: Log class name, operation type etc.
            on_deprecated_name_usage(
                "'{old}' attribute is deprecated, use '{new}' instead.".format(
                    new=new_name, old=name))
            return setattr(self, new_name, value)
        else:
            object.__setattr__(self, name, value)

    @property
    def __compat_attrs(self):
        # It's unreliable to initialize attributes in __init__() since
        # old-style classes are used and parent initializers are mostly
        # not called.
        if "_compat_attrs_mapping" not in self.__dict__:
            self.__dict__["_compat_attrs_mapping"] = {}
        return self._compat_attrs_mapping

    def _registerOldWorkerAttr(self, attr_name, pattern=None, name=None):
        """Define old-named attribute inside class instance."""
        if name is not None:
            assert pattern is None
            compat_name = name
        else:
            compat_name = deprecated_name(attr_name, pattern=pattern)
        assert compat_name not in self.__dict__
        assert compat_name not in self.__compat_attrs
        self.__compat_attrs[compat_name] = attr_name
