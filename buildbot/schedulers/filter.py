import re, types

class _NO: pass # sentinel
class ChangeFilter(object):
    def __init__(self,
            # gets a Change object, returns boolean
            filter_fn=None,
            # change attribute comparisons: exact match to PROJECT, member of
            # list PROJECTS, regular expression match to PROJECT_RE, or
            # PROJECT_FN returns True when called with the project; repository,
            # branch, and so on are similar.  Note that the regular expressions
            # are anchored to the first character of the string.  For convenience,
            # a list can also be specified to the singular option (e.g,. PROJETS
            project=_NO, project_re=_NO, project_fn=_NO,
            repository=_NO, repository_re=_NO, repository_fn=_NO,
            branch=_NO, branch_re=_NO, branch_fn=_NO,
            category=_NO, category_re=_NO, category_fn=_NO):
        def mklist(x):
            if x is not _NO and type(x) is not types.ListType:
                return [ x ]
            return x
        def mkre(r):
            if r is not _NO and not hasattr(r, 'match'):
                r = re.compile(r)
            return r

        self.filter_fn = filter_fn
        self.checks = [
                (mklist(project), mkre(project_re), project_fn, "project"),
                (mklist(repository), mkre(repository_re), repository_fn, "repository"),
                (mklist(branch), mkre(branch_re), branch_fn, "branch"),
                (mklist(category), mkre(category_re), category_fn, "category"),
            ]

    def filter_change(self, change):
        if self.filter_fn is not None and not self.filter_fn(change):
            return False
        for (filt_list, filt_re, filt_fn, chg_attr) in self.checks:
            chg_val = getattr(change, chg_attr, '')
            if filt_list is not _NO and chg_val not in filt_list:
                return False
            if filt_re is not _NO and not filt_re.match(chg_val):
                return False
            if filt_fn is not _NO and not filt_fn(chg_val):
                return False
        return True
