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


import contextlib


class ConfigErrors(Exception):
    def __init__(self, errors=None):
        if errors is None:
            errors = []
        self.errors = errors[:]

    def __str__(self):
        return "\n".join(self.errors)

    def addError(self, msg):
        self.errors.append(msg)

    def merge(self, errors):
        self.errors.extend(errors.errors)

    def __bool__(self):
        return bool(len(self.errors))


_errors = None


def error(error, always_raise=False):
    if _errors is not None and not always_raise:
        _errors.addError(error)
    else:
        raise ConfigErrors([error])


@contextlib.contextmanager
def capture_config_errors(raise_on_error=False):
    global _errors
    prev_errors = _errors
    _errors = errors = ConfigErrors()
    try:
        yield errors
    except ConfigErrors as e:
        errors.merge(e)
    finally:
        _errors = prev_errors

    if raise_on_error and errors:
        raise errors
