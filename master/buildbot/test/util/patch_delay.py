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
# Portions of this file include source code of Python 3.7 from
# cpython/Lib/unittest/mock.py file.
#
# It is licensed under PYTHON SOFTWARE FOUNDATION LICENSE VERSION 2.
# Copyright (c) 2001-2019 Python Software Foundation. All rights reserved.

import contextlib
import functools

import mock

from twisted.internet import defer


def _dot_lookup(thing, comp, import_path):
    try:
        return getattr(thing, comp)
    except AttributeError:
        __import__(import_path)
        return getattr(thing, comp)


def _importer(target):
    components = target.split('.')
    import_path = components.pop(0)
    thing = __import__(import_path)

    for comp in components:
        import_path += ".%s" % comp
        thing = _dot_lookup(thing, comp, import_path)
    return thing


def _get_target(target):
    try:
        target, attribute = target.rsplit('.', 1)
    except (TypeError, ValueError):
        raise TypeError("Need a valid target to patch. You supplied: %r" %
                        (target,))
    return _importer(target), attribute


class DelayWrapper:
    def __init__(self):
        self._deferreds = []

    def add_new(self):
        d = defer.Deferred()
        self._deferreds.append(d)
        return d

    def __len__(self):
        return len(self._deferreds)

    def fire(self):
        deferreds = self._deferreds
        self._deferreds = []
        for d in deferreds:
            d.callback(None)


@contextlib.contextmanager
def patchForDelay(target_name):
    class Default:
        pass
    default = Default()

    target, attribute = _get_target(target_name)
    original = getattr(target, attribute, default)

    if original is default:
        raise Exception('Could not find name {}'.format(target_name))
    if not callable(original):
        raise Exception('{} is not callable'.format(target_name))

    delay = DelayWrapper()

    @functools.wraps(original)
    @defer.inlineCallbacks
    def wrapper(*args, **kwargs):
        yield delay.add_new()
        return (yield original(*args, **kwargs))

    with mock.patch(target_name, new=wrapper):
        try:
            yield delay
        finally:
            delay.fire()
