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

from sphinx.domains import Index
from sphinx.domains.std import StandardDomain


class PythonAPIIndex(Index):

    objecttype = 'class'
    name = 'apiindex'
    localname = 'Public API Index'
    shortname = 'classes'

    def generate(self, docnames=None):
        unsorted_objects = [(refname, entry.docname, entry.objtype)
                            for (refname, entry) in self.domain.data['objects'].items()
                            if entry.objtype in ['class', 'function']]
        objects = sorted(unsorted_objects,
                         key=lambda x: x[0].lower())

        entries = []

        for refname, docname, objtype in objects:
            if docnames and docname not in docnames:
                continue

            extra_info = objtype
            display_name = refname
            if objtype == 'function':
                display_name += '()'
            entries.append([display_name, 0, docname, refname, extra_info, '', ''])

        return [('', entries)], False


def setup(app):
    app.add_index_to_domain('py', PythonAPIIndex)
    StandardDomain.initial_data['labels']['apiindex'] = ('py-apiindex', '', 'Public API Index')
    StandardDomain.initial_data['anonlabels']['apiindex'] = ('py-apiindex', '')
    return {'parallel_read_safe': True, 'parallel_write_safe': True}
