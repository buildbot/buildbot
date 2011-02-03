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

import re, types

from buildbot.util import ComparableMixin, NotABranch

class ChangeFilter(ComparableMixin):

    # NOTE: If users use a filter_fn, we have no way to determine whether it has
    # changed at reconfig, so the scheduler will always be restarted.  That's as
    # good as Python can do.
    compare_attrs = ('filter_fn', 'checks')

    def __init__(self,
            # gets a Change object, returns boolean
            filter_fn=None,
            # change attribute comparisons: exact match to PROJECT, member of
            # list PROJECTS, regular expression match to PROJECT_RE, or
            # PROJECT_FN returns True when called with the project; repository,
            # branch, and so on are similar.  Note that the regular expressions
            # are anchored to the first character of the string.  For convenience,
            # a list can also be specified to the singular option (e.g,. PROJETS
            project=None, project_re=None, project_fn=None,
            repository=None, repository_re=None, repository_fn=None,
            branch=NotABranch, branch_re=None, branch_fn=None,
            category=None, category_re=None, category_fn=None):
        def mklist(x):
            if x is not None and type(x) is not types.ListType:
                return [ x ]
            return x
        def mklist_br(x): # branch needs to be handled specially
            if x is NotABranch:
                return None
            if type(x) is not types.ListType:
                return [ x ]
            return x
        def mkre(r):
            if r is not None and not hasattr(r, 'match'):
                r = re.compile(r)
            return r

        self.filter_fn = filter_fn
        self.checks = [
                (mklist(project), mkre(project_re), project_fn, "project"),
                (mklist(repository), mkre(repository_re), repository_fn, "repository"),
                (mklist_br(branch), mkre(branch_re), branch_fn, "branch"),
                (mklist(category), mkre(category_re), category_fn, "category"),
            ]

    def filter_change(self, change):
        if self.filter_fn is not None and not self.filter_fn(change):
            return False
        for (filt_list, filt_re, filt_fn, chg_attr) in self.checks:
            chg_val = getattr(change, chg_attr, '')
            if filt_list is not None and chg_val not in filt_list:
                return False
            if filt_re is not None and (chg_val is None or not filt_re.match(chg_val)):
                return False
            if filt_fn is not None and not filt_fn(chg_val):
                return False
        return True

    def __repr__(self):
        checks = []
        for (filt_list, filt_re, filt_fn, chg_attr) in self.checks:
            if filt_list is not None and len(filt_list) == 1:
                checks.append('%s == %s' % (chg_attr, filt_list[0]))
            elif filt_list is not None:
                checks.append('%s in %r' % (chg_attr, filt_list))
            if filt_re is not None :
                checks.append('%s ~/%s/' % (chg_attr, filt_re))
            if filt_fn is not None :
                checks.append('%s(%s)' % (filt_fn.__name__, chg_attr))

        return "<%s on %s>" % (self.__class__.__name__, ' and '.join(checks))

    @staticmethod
    def fromSchedulerConstructorArgs(change_filter=None,
            branch=NotABranch, categories=None):

        """
        Static method to create a filter based on constructor args
        change_filter, branch, and categories; use default values @code{None},
        @code{NotABranch}, and @code{None}, respectively.  These arguments are
        interpreted as documented for the
        L{buildbot.schedulers.basic.Scheduler} class.

        @returns: L{ChangeFilter} instance or None for not filtering
        """

        # use a change_filter, if given one
        if change_filter:
            if (branch is not NotABranch or categories is not None):
                raise RuntimeError("cannot specify both change_filter and "
                                   "branch or categories")
            return change_filter
        elif branch is not NotABranch or categories:
            # build a change filter from the deprecated category and branch args
            cfargs = {}
            if branch is not NotABranch: cfargs['branch'] = branch
            if categories: cfargs['category'] = categories
            return ChangeFilter(**cfargs)
        else:
            return None
