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

from __future__ import absolute_import
from __future__ import print_function
from future.utils import iteritems

import functools
import sys
import warnings

from twisted.python.deprecate import deprecatedModuleAttribute as _deprecatedModuleAttribute
from twisted.python.deprecate import getWarningMethod
from twisted.python.deprecate import setWarningMethod
from twisted.python.versions import Version

__all__ = (
    "DeprecatedWorkerNameWarning",
    "deprecatedWorkerClassMethod",
    "WorkerAPICompatMixin",
    "setupWorkerTransition",
    "deprecatedWorkerModuleAttribute",
    "reportDeprecatedWorkerNameUsage",
    "reportDeprecatedWorkerModuleUsage",
)


_WORKER_WARNING_MARK = "[WORKER]"


def _compat_name(new_name, compat_name=None):
    """Returns old API ("slave") name for new name ("worker").

    >>> assert _compat_name("Worker") == "Slave"
    >>> assert _compat_name("SomeWorkerStuff") == "SomeSlaveStuff"
    >>> assert _compat_name("SomeWorker", compat_name="SomeBuildSlave") == \
        "SomeBuildSlave"

    If `compat_name` is not specified old name is construct by replacing in
    `new_name`:
        "worker" -> "slave",
        "Worker" -> "Slave".

    For the sake of simplicity of usage if `compat_name` argument is specified
    it will returned as the result.
    """

    if compat_name is not None:
        assert "slave" in compat_name.lower()
        assert new_name == "" or "worker" in new_name.lower(), new_name
        return compat_name

    compat_replacements = {
        "worker": "slave",
        "Worker": "Slave",
    }

    compat_name = new_name
    assert "slave" not in compat_name.lower()
    assert "worker" in compat_name.lower()
    for new_word, old_word in iteritems(compat_replacements):
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


def reportDeprecatedWorkerNameUsage(message, stacklevel=None, filename=None,
                                    lineno=None):
    """Hook that is ran when old API name is used.

    :param stacklevel: stack level relative to the caller's frame.
    Defaults to caller of the caller of this function.
    """

    if filename is None:
        if stacklevel is None:
            # Warning will refer to the caller of the caller of this function.
            stacklevel = 3
        else:
            stacklevel += 2

        warnings.warn(DeprecatedWorkerNameWarning(message), None, stacklevel)

    else:
        assert stacklevel is None

        if lineno is None:
            lineno = 0

        warnings.warn_explicit(
            DeprecatedWorkerNameWarning(message),
            DeprecatedWorkerNameWarning,
            filename, lineno)


def reportDeprecatedWorkerModuleUsage(message, stacklevel=None):
    """Hook that is ran when old API module is used.

    :param stacklevel: stack level relative to the caller's frame.
    Defaults to caller of the caller of this function.
    """

    if stacklevel is None:
        # Warning will refer to the caller of the caller of this function.
        stacklevel = 3
    else:
        stacklevel += 2

    warnings.warn(DeprecatedWorkerModuleWarning(message), None, stacklevel)


def setupWorkerTransition():
    """Hook Twisted deprecation machinery to use custom warning class
    for Worker API deprecation warnings."""

    default_warn_method = getWarningMethod()

    def custom_warn_method(message, category, stacklevel):
        if stacklevel is not None:
            stacklevel += 1
        if _WORKER_WARNING_MARK in message:
            # Message contains our mark - it's Worker API Renaming warning,
            # issue it appropriately.
            message = message.replace(_WORKER_WARNING_MARK, "")
            warnings.warn(
                DeprecatedWorkerNameWarning(message), message, stacklevel)
        else:
            # Other's warning message
            default_warn_method(message, category, stacklevel)

    setWarningMethod(custom_warn_method)


def deprecatedWorkerModuleAttribute(scope, attribute, compat_name=None,
                                    new_name=None):
    """This is similar to Twisted's deprecatedModuleAttribute, but for
    Worker API Rename warnings.

    Can be used to create compatibility attributes for module-level classes,
    functions and global variables.

    :param scope: module scope (locals() in the context of a module)
    :param attribute: module object (class, function, global variable)
    :param compat_name: optional compatibility name (will be generated if not
    specified)
    :param new_name: optional new name (will be used name of attribute object
    in the module is not specified). If empty string is specified, then no
    new name is assumed for this attribute.
    """

    module_name = scope["__name__"]
    assert module_name in sys.modules, "scope must be module, i.e. locals()"
    assert sys.modules[module_name].__dict__ is scope, \
        "scope must be module, i.e. locals()"

    if new_name is None:
        scope_keys = list(scope.keys())
        scope_values = list(scope.values())
        attribute_name = scope_keys[scope_values.index(attribute)]
    else:
        attribute_name = new_name

    compat_name = _compat_name(attribute_name, compat_name=compat_name)

    scope[compat_name] = attribute

    if attribute_name:
        msg = "Use {0} instead.".format(attribute_name)
    else:
        msg = "Don't use it."

    _deprecatedModuleAttribute(
        Version("Buildbot", 0, 9, 0),
        _WORKER_WARNING_MARK + msg,
        module_name, compat_name)


def deprecatedWorkerClassProperty(scope, prop, compat_name=None,
                                  new_name=None):
    """Define compatibility class property.

    Can be used to create compatibility attribute for class property.

    :param scope: class scope (locals() in the context of a scope)
    :param prop: property object for which compatibility name should be
    created.
    :param compat_name: optional compatibility name (will be generated if not
    specified)
    :param new_name: optional new name (will be used name of attribute object
    in the module is not specified). If empty string is specified, then no
    new name is assumed for this attribute.
    """

    if new_name is None:
        scope_keys = list(scope.keys())
        scope_values = list(scope.values())
        attribute_name = scope_keys[scope_values.index(prop)]
    else:
        attribute_name = new_name

    compat_name = _compat_name(attribute_name, compat_name=compat_name)

    if attribute_name:
        advice_msg = "use '{0}' instead".format(attribute_name)
    else:
        advice_msg = "don't use it"

    def get(self):
        reportDeprecatedWorkerNameUsage(
            "'{old}' property is deprecated, "
            "{advice}.".format(
                old=compat_name, advice=advice_msg))
        return getattr(self, attribute_name)

    assert compat_name not in scope
    scope[compat_name] = property(get)


def deprecatedWorkerClassMethod(scope, method, compat_name=None):
    """Define old-named method inside class."""
    method_name = method.__name__

    compat_name = _compat_name(method_name, compat_name=compat_name)

    assert compat_name not in scope

    def old_method(self, *args, **kwargs):
        reportDeprecatedWorkerNameUsage(
            "'{old}' method is deprecated, use '{new}' instead.".format(
                new=method_name, old=compat_name))
        return getattr(self, method_name)(*args, **kwargs)

    functools.update_wrapper(old_method, method)

    scope[compat_name] = old_method


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
        reportDeprecatedWorkerNameUsage(
            "'{old}' attribute is deprecated, use '{new}' instead.".format(
                new=new_name, old=name))

        return getattr(self, new_name)

    def __setattr__(self, name, value):
        if name in self.__compat_attrs:
            new_name = self.__compat_attrs[name]
            # TODO: Log class name, operation type etc.
            reportDeprecatedWorkerNameUsage(
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

    def _registerOldWorkerAttr(self, attr_name, name=None):
        """Define old-named attribute inside class instance."""
        compat_name = _compat_name(attr_name, compat_name=name)
        assert compat_name not in self.__dict__
        assert compat_name not in self.__compat_attrs
        self.__compat_attrs[compat_name] = attr_name


# Enable worker transition hooks
setupWorkerTransition()
