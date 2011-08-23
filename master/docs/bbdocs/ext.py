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

from docutils import nodes
from sphinx.domains import Domain, ObjType
from sphinx.roles import XRefRole
from sphinx.util.compat import Directive
from sphinx.util import ws_re
from sphinx.util.nodes import make_refnode
from sphinx import addnodes

class BBCfgDirective(Directive):
    indextemplate = 'single: BuildMaster Config; %s'

    has_content = False
    required_arguments = 1
    optional_arguments = 0
    final_argument_whitespace = True
    option_spec = {}

    def run(self):
        env = self.state.document.settings.env
        # normalize whitespace in fullname like XRefRole does
        fullname = ws_re.sub(' ', self.arguments[0].strip())
        targetname = '%s-%s' % (self.name, fullname)

        # keep the target
        env.domaindata['bb']['cfg-targets'][fullname] = env.docname, targetname

        # make up the descriptor: an index entry and a target
        inode = addnodes.index(entries=[
            ('single', 'Buildmaster Config; %s' % (fullname,), targetname,
                targetname),
        ])
        node = nodes.target('', '', ids=[targetname])
        ret = [inode, node]

        # add the target to the document
        self.state.document.note_explicit_target(node)

        return ret 

class BBDomain(Domain):
    name = 'bb'
    label = 'Buildbot'

    object_types = {
        'cfg' : ObjType('cfg', 'cfg'),
    }

    directives = {
        'cfg' : BBCfgDirective,
    }

    roles = {
        'cfg' : XRefRole(),
    }

    initial_data = {
        'objects' : {}, # (objtype, shortname) -> (docname, targetname)
        'cfg-targets' : {} # cfg param name -> (docname, targetname)
    }

    def resolve_xref(self, env, fromdocname, builder, typ, target, node,
                     contnode):
        map = self.data['%s-targets' % typ]
        try:
            todocname, targetname = map[target]
        except KeyError:
            return None
        return make_refnode(builder, fromdocname,
                            todocname, targetname,
                            contnode, target)

        objects = self.data['objects']
        print objects
        objtypes = self.objtypes_for_role(typ)
        for objtype in objtypes:
            if (objtype, target) in objects:
                todocname, target = objects[objtype, target]

def setup(app):
    app.add_domain(BBDomain)
