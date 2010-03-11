import re, types

from buildbot.util import ComparableMixin, NotABranch

class ChangeFilter(ComparableMixin):

    # TODO: filter_fn will always be different.  Does that mean that we always
    # reconfigure schedulers?  Is that a problem?
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
            if filt_re is not None and not filt_re.match(chg_val):
                return False
            if filt_fn is not None and not filt_fn(chg_val):
                return False
        return True
