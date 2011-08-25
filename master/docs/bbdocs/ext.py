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
from sphinx.domains import Domain, ObjType, Index
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
        targets = env.domaindata['bb']['targets'].setdefault('cfg', {})
        targets[fullname] = env.docname, targetname

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


class BBSchedDirective(Directive):
    indextemplate = 'single: Scheduler; %s'

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
        targets = env.domaindata['bb']['targets'].setdefault('sched', {})
        targets[fullname] = env.docname, targetname

        # make up the descriptor: an index entry and a target
        inode = addnodes.index(entries=[
            ('single', 'Scheduler; %s' % (fullname,), targetname,
                targetname),
        ])
        node = nodes.target('', '', ids=[targetname])
        ret = [inode, node]

        # add the target to the document
        self.state.document.note_explicit_target(node)

        return ret 


class BBCfgIndex(Index):
    name = "cfg"
    localname = "Buildmaster Configuration Index"

    def generate(self, docnames=None):
        content = {}
        idx_targets = self.domain.data['targets'].get('cfg', {})
        for name, (docname, targetname) in idx_targets.iteritems():
            letter = name[0].lower()
            content.setdefault(letter, []).append(
                (name, 0, docname, targetname, '', '', ''))
        content = [ (l, content[l])
                    for l in sorted(content.keys()) ]
        return (content, False)


class BBSchedIndex(Index):
    name = "sched"
    localname = "Scheduler Index"

    def generate(self, docnames=None):
        content = {}
        idx_targets = self.domain.data['targets'].get('sched', {})
        for name, (docname, targetname) in idx_targets.iteritems():
            letter = name[0].lower()
            content.setdefault(letter, []).append(
                (name, 0, docname, targetname, '', '', ''))
        content = [ (l, content[l])
                    for l in sorted(content.keys()) ]
        return (content, False)


class BBDomain(Domain):
    name = 'bb'
    label = 'Buildbot'

    object_types = {
        'cfg' : ObjType('cfg', 'cfg'),
        'sched' : ObjType('sched', 'sched'),
    }

    directives = {
        'cfg' : BBCfgDirective,
        'sched' : BBSchedDirective,
    }

    roles = {
        'cfg' : XRefRole(),
        'sched' : XRefRole(),
        'index' : XRefRole(),
    }

    initial_data = {
        'targets' : {}, # kind -> target -> (docname, targetname)
    }

    indices = [
        BBCfgIndex,
        BBSchedIndex,
    ]

    def resolve_index_ref(self, env, fromdocname, builder, typ, target, node,
                     contnode):
        # find the index object, to get its full name
        for idx in self.indices:
            if idx.name == target:
                break
        else:
            raise KeyError("no index named '%s'" % target)

        # indexes appear to be automatically generated at doc DOMAIN-NAME
        todocname = "bb-%s" % target

        node = nodes.reference('', '', internal=True)
        node['refuri'] = builder.get_relative_uri(fromdocname, todocname)
        node['reftitle'] = idx.localname
        node.append(nodes.emphasis(idx.localname, idx.localname))
        return node

    def resolve_xref(self, env, fromdocname, builder, typ, target, node,
                     contnode):
        if typ == 'index':
            return self.resolve_index_ref(env, fromdocname, builder, typ,
                                        target, node, contnode)
        map = self.data['targets'].get(typ, {})
        try:
            todocname, targetname = map[target]
        except KeyError:
            return None
        return make_refnode(builder, fromdocname,
                            todocname, targetname,
                            contnode, target)

def setup(app):
    app.add_domain(BBDomain)
