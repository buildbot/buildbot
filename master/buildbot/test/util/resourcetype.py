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

from buildbot.util import json
from buildbot.data import base

class ResourceTypeVerifier(object):

    def __init__(self, name, attrs={}):
        """
        @param attrs: dict mapping name to type; types are given in
            _makeValidators, below.  any type can have a suffix ":none"
            allowing its value to be None
        """
        self.name = name
        self.attrs = attrs

        self.validators = self._makeValidators(attrs)

    def __call__(self, testcase, res):
        testcase.assertIsInstance(res, dict)

        problems = []
        res_keys = set(res)
        exp_keys = set(self.attrs)
        if res_keys != exp_keys:
            unk_keys = res_keys - exp_keys
            missing_keys = exp_keys - res_keys
            if unk_keys:
                problems.append("unknown key%s %s"
                    % ('s' if len(unk_keys) > 1 else '',
                       ', '.join(map(repr, unk_keys))))
            if missing_keys:
                problems.append("missing key%s %s"
                    % ('s' if len(missing_keys) > 1 else '',
                       ', '.join(map(repr, missing_keys))))

        for k in res_keys & exp_keys:
            if not self.validators[k](res[k]):
                problems.append('value for "%s" does not match type %s' %
                        (k, self.attrs[k]))

        if problems:
            msg = "%r is not a %s: " % (res, self.name,)
            msg += '; '.join(problems)
            testcase.fail(msg)

    def _makeValidators(self, attrs):
        # helper functions
        def orNone(valfn):
            return lambda v : v is None or valfn(v)

        def stringlist(value):
            if not isinstance(value, list):
                return False
            for x in value:
                if not isinstance(x, unicode):
                    return False
            return True

        def sourcedProperties(value):
            if not isinstance(value, dict):
                return False
            for k, v in value.iteritems():
                if not isinstance(k, unicode):
                    return False
                if not isinstance(v, tuple):
                    return False
                if not 2 == len(v):
                    return False
                propval, propsrc = v
                if not isinstance(propsrc, unicode):
                    return False
                try:
                    json.dumps(propval)
                except:
                    return False
            return True

        validators = {}
        for name, typ in attrs.iteritems():
            noneok = typ.endswith(':none')
            if noneok:
                typ = typ[:-5]

            if typ == 'integer':
                valfn = lambda v : isinstance(v, int)
            elif typ == 'string':
                # note that we intentionally *enforce* unicode!
                valfn = lambda v : isinstance(v, unicode)
            elif typ == 'stringlist':
                valfn = stringlist
            elif typ == 'sourcedProperties':
                valfn = sourcedProperties
            elif typ == 'Link':
                valfn = lambda v : isinstance(v, base.Link)
            else:
                raise RuntimeError('invalid type %s' % typ)

            validators[name] = orNone(valfn) if noneok else valfn

        return validators

# concrete verifiers for documented resource types

verifyChange = ResourceTypeVerifier('change',
    attrs = dict(
        changeid='integer',
        author='string',
        files='stringlist',
        comments='string',
        revision='string:none',
        when_timestamp='integer',
        branch='string:none',
        category='string:none',
        revlink='string:none',
        properties='sourcedProperties',
        repository='string',
        project='string',
        codebase='string',
        link='Link',
        ))
