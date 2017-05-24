# coding=utf-8
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

from __future__ import absolute_import
from __future__ import print_function
from future.utils import lrange

import os

from twisted.internet import process
from twisted.python import log


def patch():
    log.msg("Applying patch for http://twistedmatrix.com/trac/ticket/4881")
    process._listOpenFDs = _listOpenFDs

#
# Everything below this line was taken verbatim from Twisted, except as
# annotated.

#
# r31474:trunk/LICENSE

# Copyright (c) 2001-2010
# Allen Short
# Andy Gayton
# Andrew Bennetts
# Antoine Pitrou
# Apple Computer, Inc.
# Benjamin Bruheim
# Bob Ippolito
# Canonical Limited
# Christopher Armstrong
# David Reid
# Donovan Preston
# Eric Mangold
# Eyal Lotem
# Itamar Shtull-Trauring
# James Knight
# Jason A. Mobarak
# Jean-Paul Calderone
# Jessica McKellar
# Jonathan Jacobs
# Jonathan Lange
# Jonathan D. Simms
# JÃ¼rgen Hermann
# Kevin Horn
# Kevin Turner
# Mary Gardiner
# Matthew Lefkowitz
# Massachusetts Institute of Technology
# Moshe Zadka
# Paul Swartz
# Pavel Pergamenshchik
# Ralph Meijer
# Sean Riley
# Software Freedom Conservancy
# Travis B. Hartwell
# Thijs Triemstra
# Thomas Herve
# Timothy Allen
#
# Permission is hereby granted, free of charge, to any person obtaining
# a copy of this software and associated documentation files (the
# "Software"), to deal in the Software without restriction, including
# without limitation the rights to use, copy, modify, merge, publish,
# distribute, sublicense, and/or sell copies of the Software, and to
# permit persons to whom the Software is furnished to do so, subject to
# the following conditions:
#
#     The above copyright notice and this permission notice shall be
#     included in all copies or substantial portions of the Software.
#
#     THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
#     EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
#     MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
#     NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE
#     LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
#     OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION
#     WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

#
# r31474:trunk/twisted/internet/process.py

# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.


class _FDDetector(object):

    """
    This class contains the logic necessary to decide which of the available
    system techniques should be used to detect the open file descriptors for
    the current process. The chosen technique gets monkey-patched into the
    _listOpenFDs method of this class so that the detection only needs to occur
    once.

    @ivars listdir: The implementation of listdir to use. This gets overwritten
        by the test cases.
    @ivars getpid: The implementation of getpid to use, returns the PID of the
        running process.
    @ivars openfile: The implementation of open() to use, by default the Python
        builtin.
    """
    # So that we can unit test this
    listdir = os.listdir
    getpid = os.getpid
    openfile = open

    def _listOpenFDs(self):
        """
        Figure out which implementation to use, then run it.
        """
        self._listOpenFDs = self._getImplementation()
        return self._listOpenFDs()

    def _getImplementation(self):
        """
        Check if /dev/fd works, if so, use that.  Otherwise, check if
        /proc/%d/fd exists, if so use that.

        Otherwise, ask resource.getrlimit, if that throws an exception, then
        fallback to _fallbackFDImplementation.
        """
        try:
            self.listdir("/dev/fd")
            if self._checkDevFDSanity():  # FreeBSD support :-)
                return self._devFDImplementation
            return self._fallbackFDImplementation
        except Exception:  # changed in Buildbot to avoid bare 'except'
            try:
                self.listdir("/proc/%d/fd" % (self.getpid(),))
                return self._procFDImplementation
            except Exception:  # changed in Buildbot to avoid bare 'except'
                try:
                    self._resourceFDImplementation()  # Imports resource
                    return self._resourceFDImplementation
                except Exception:  # changed in Buildbot to avoid bare 'except'
                    return self._fallbackFDImplementation

    def _checkDevFDSanity(self):
        """
        Returns true iff opening a file modifies the fds visible
        in /dev/fd, as it should on a sane platform.
        """
        start = self.listdir("/dev/fd")
        self.openfile("/dev/null", "r")  # changed in Buildbot to hush pyflakes
        end = self.listdir("/dev/fd")
        return start != end

    def _devFDImplementation(self):
        """
        Simple implementation for systems where /dev/fd actually works.
        See: http://www.freebsd.org/cgi/man.cgi?fdescfs
        """
        dname = "/dev/fd"
        result = [int(fd) for fd in os.listdir(dname)]
        return result

    def _procFDImplementation(self):
        """
        Simple implementation for systems where /proc/pid/fd exists (we assume
        it works).
        """
        dname = "/proc/%d/fd" % (os.getpid(),)
        return [int(fd) for fd in os.listdir(dname)]

    def _resourceFDImplementation(self):
        """
        Fallback implementation where the resource module can inform us about
        how many FDs we can expect.

        Note that on OS-X we expect to be using the /dev/fd implementation.
        """
        import resource
        maxfds = resource.getrlimit(resource.RLIMIT_NOFILE)[1] + 1
        # OS-X reports 9223372036854775808. That's a lot of fds
        # to close
        if maxfds > 1024:
            maxfds = 1024
        return lrange(maxfds)

    def _fallbackFDImplementation(self):
        """
        Fallback-fallback implementation where we just assume that we need to
        close 256 FDs.
        """
        maxfds = 256
        return lrange(maxfds)


detector = _FDDetector()


def _listOpenFDs():
    """
    Use the global detector object to figure out which FD implementation to
    use.
    """
    return detector._listOpenFDs()
