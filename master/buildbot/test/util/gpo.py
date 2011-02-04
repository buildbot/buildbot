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

from twisted.internet import defer, utils

class GetProcessOutputMixin:
    """

    Mixin class to help with patching Twisted's getProcessOutput.

    Call addGetProcessOutputResult(pattern, result), where pattern is one of
    the gpo*Pattern methods, and result is the expected result, which will be
    wrapped in a deferred.  If result is callable, it will be called with the
    same arguments as getProcessOutput or getProcessOutputAndvalue, and its
    result returned (wrapped in a deferred, if necessary).  Note that as each
    pattern matches, it is removed from the list, so the same command may be
    patched to return a sequence of values by adding the same pattern several
    times.

    addGetProcessOutputAndValueResult(pattern, result) works similarly for
    patching getProcessOutputAndValue, although note that its result is a
    three-tuple (stdout, stderr, rc).

    """

    def setUpGetProcessOutput(self):
        self._gpo_patched = False
        self._gpo_patterns = []
        self._gpoav_patterns = []

    def tearDownGetProcessOutput(self):
        pass

    def _patched(self, patlist, bin, args, **kwargs):
        for i, (pattern, result) in enumerate(patlist):
            if pattern(bin, args, **kwargs):
                del patlist[i]
                if callable(result):
                    result = result(bin, args, **kwargs)
                return defer.maybeDeferred(lambda : result)
        return defer.fail(RuntimeError("no matching command for %s" % (args,)))

    # these can be overridden if necessary
    def patched_getProcessOutput(self, bin, args, env=None, **kwargs):
        return self._patched(self._gpo_patterns, bin, args, env=env, **kwargs)

    def patched_getProcessOutputAndValue(self, bin, args, env=None, **kwargs):
        return self._patched(self._gpoav_patterns, bin, args, env=env, **kwargs)

    def _patch_gpo(self):
        if not self._gpo_patched:
            self.patch(utils, "getProcessOutput",
                            self.patched_getProcessOutput)
            self.patch(utils, "getProcessOutputAndValue",
                            self.patched_getProcessOutputAndValue)
            self._gpo_patched = True

    def addGetProcessOutputResult(self, pattern, result):
        self._patch_gpo()
        self._gpo_patterns.append((pattern, result))

    def addGetProcessOutputAndValueResult(self, pattern, result):
        self._patch_gpo()
        self._gpoav_patterns.append((pattern, result))

    def gpoCommandPattern(self, commandSuffix):
        "Matches if the command ends with commandSuffix, e.g., 'svn'"
        def matchesCommandSuffix(bin, args, **kwargs):
            return bin.endswith(commandSuffix)
        return matchesCommandSuffix

    def gpoSubcommandPattern(self, commandSuffix, subcommand):
        """Matches if the command ends with commandSuffix and has the given
        subcommand in args[1], e.g., 'svn', 'update'"""
        def matchesSubcommand(bin, args, **kwargs):
            return bin.endswith(commandSuffix) and args[0] == subcommand
        return matchesSubcommand

    def gpoAnyPattern(self):
        return lambda bin, args, **kwargs : True
