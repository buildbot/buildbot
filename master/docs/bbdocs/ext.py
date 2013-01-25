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


class BBRefTargetDirective(Directive):
    """
    A directive that can be a target for references.  Attributes:

    @cvar ref_type: same as directive name
    @cvar indextemplates: templates for main index entries, if any
    """

    has_content = False
    required_arguments = 1
    optional_arguments = 0
    final_argument_whitespace = True
    option_spec = {}

    def run(self):
        env = self.state.document.settings.env
        # normalize whitespace in fullname like XRefRole does
        fullname = ws_re.sub(' ', self.arguments[0].strip())
        targetname = '%s-%s' % (self.ref_type, fullname)

        # keep the target; this may be used to generate a BBIndex later
        targets = env.domaindata['bb']['targets'].setdefault(self.ref_type, {})
        targets[fullname] = env.docname, targetname

        # make up the descriptor: a target and potentially an index descriptor
        node = nodes.target('', '', ids=[targetname])
        ret = [node]

        # add the target to the document
        self.state.document.note_explicit_target(node)

        # append the index node if necessary
        entries = []
        for tpl in self.indextemplates:
            colon = tpl.find(':')
            if colon != -1:
                indextype = tpl[:colon].strip()
                indexentry = tpl[colon+1:].strip() % (fullname,)
            else:
                indextype = 'single'
                indexentry = tpl % (fullname,)
            entries.append((indextype, indexentry, targetname, targetname))

        if entries:
            inode = addnodes.index(entries=entries)
            ret.insert(0, inode)

        return ret 

    @classmethod
    def resolve_ref(cls, domain, env, fromdocname, builder, typ, target, node,
                     contnode):
        """
        Resolve a reference to a directive of this class
        """
        targets = domain.data['targets'].get(cls.ref_type, {})
        try:
            todocname, targetname = targets[target]
        except KeyError:
            print "MISSING BB REFERENCE: bb:%s:%s" % (cls.ref_type, target)
            return None

        return make_refnode(builder, fromdocname,
                            todocname, targetname,
                            contnode, target)


def make_ref_target_directive(ref_type, indextemplates=None):
    """
    Create and return a L{BBRefTargetDirective} subclass.
    """
    return type("BB%sRefTargetDirective" % (ref_type.capitalize(),),
                (BBRefTargetDirective,),
                dict(ref_type=ref_type, indextemplates=indextemplates))


class BBIndex(Index):
    """
    A Buildbot-specific index.

    @cvar name: same name as the directive and xref role
    @cvar localname: name of the index document
    """

    def generate(self, docnames=None):
        content = {}
        idx_targets = self.domain.data['targets'].get(self.name, {})
        for name, (docname, targetname) in idx_targets.iteritems():
            letter = name[0].upper()
            content.setdefault(letter, []).append(
                (name, 0, docname, targetname, '', '', ''))
        content = [ (l, sorted(content[l], key=lambda tup : tup[0].lower()))
                    for l in sorted(content.keys()) ]
        return (content, False)

    @classmethod
    def resolve_ref(cls, domain, env, fromdocname, builder, typ, target, node,
                     contnode):
        """
        Resolve a reference to an index to the document containing the index,
        using the index's C{localname} as the content of the link.
        """
        # indexes appear to be automatically generated at doc DOMAIN-NAME
        todocname = "bb-%s" % target

        node = nodes.reference('', '', internal=True)
        node['refuri'] = builder.get_relative_uri(fromdocname, todocname)
        node['reftitle'] = cls.localname
        node.append(nodes.emphasis(cls.localname, cls.localname))
        return node


def make_index(name, localname):
    """
    Create and return a L{BBIndex} subclass, for use in the domain's C{indices}
    """
    return type("BB%sIndex" % (name.capitalize(),),
                (BBIndex,),
                dict(name=name, localname=localname))

class BugRole(object):
    """
    A role to create a link to a Trac bug, by number
    """

    def __call__(self, typ, rawtext, text, lineno, inliner,
                 options={}, content=[]):
        bugnum = text.lstrip('#')
        node = nodes.reference('', '')
        node['refuri'] = 'http://trac.buildbot.net/ticket/%s' % bugnum
        node['reftitle'] = title = 'bug #%s' % bugnum
        node.append(nodes.Text(title))
        return [ node ], []


class SrcRole(object):
    """
    A role to link to buildbot source on master
    """

    def __call__(self, typ, rawtext, text, lineno, inliner,
                 options={}, content=[]):
        node = nodes.reference('', '')
        node['refuri'] = (
            'https://github.com/buildbot/buildbot/blob/master/%s' % text )
        node['reftitle'] = title = '%s' % text
        node.append(nodes.literal(title, title))
        return [ node ], []


class PullRole(object):
    """
    A role to link to a buildbot pull request
    """

    def __call__(self, typ, rawtext, text, lineno, inliner,
                 options={}, content=[]):
        node = nodes.reference('', '')
        node['refuri'] = ('https://github.com/buildbot/buildbot/pull/' + text)
        node['reftitle'] = title = 'pull request %s' % text
        node.append(nodes.Text(title, title))
        return [ node ], []


class BBDomain(Domain):
    name = 'bb'
    label = 'Buildbot'

    object_types = {
        'cfg' : ObjType('cfg', 'cfg'),
        'sched' : ObjType('sched', 'sched'),
        'chsrc' : ObjType('chsrc', 'chsrc'),
        'step' : ObjType('step', 'step'),
        'status' : ObjType('status', 'status'),
        'cmdline' : ObjType('cmdline', 'cmdline'),
    }

    directives = {
        'cfg' : make_ref_target_directive('cfg',
                indextemplates=[
                    'single: Buildmaster Config; %s',
                    'single: %s (Buildmaster Config)',
                ]),
        'sched' : make_ref_target_directive('sched',
                indextemplates=[
                    'single: Schedulers; %s',
                    'single: %s Scheduler',
                ]),
        'chsrc' : make_ref_target_directive('chsrc',
                indextemplates=[
                    'single: Change Sources; %s',
                    'single: %s Change Source',
                ]),
        'step' : make_ref_target_directive('step',
                indextemplates=[
                    'single: Build Steps; %s',
                    'single: %s Build Step',
                ]),
        'status' : make_ref_target_directive('status',
                indextemplates=[
                    'single: Status Targets; %s',
                    'single: %s Status Target',
                ]),
        'cmdline' : make_ref_target_directive('cmdline',
                indextemplates=[
                    'single: Command Line Subcommands; %s',
                    'single: %s Command Line Subcommand',
                ]),
    }

    roles = {
        'cfg' : XRefRole(),
        'sched' : XRefRole(),
        'chsrc' : XRefRole(),
        'step' : XRefRole(),
        'status' : XRefRole(),
        'cmdline' : XRefRole(),

        'index' : XRefRole(),

        'bug' : BugRole(),
        'src' : SrcRole(),
        'pull' : PullRole(),
    }

    initial_data = {
        'targets' : {}, # type -> target -> (docname, targetname)
    }

    indices = [
        make_index("cfg", "Buildmaster Configuration Index"),
        make_index("sched", "Scheduler Index"),
        make_index("chsrc", "Change Source Index"),
        make_index("step", "Build Step Index"),
        make_index("status", "Status Target Index"),
        make_index("cmdline", "Command Line Index"),
    ]

    def resolve_xref(self, env, fromdocname, builder, typ, target, node,
                     contnode):
        if typ == 'index':
            for idx in self.indices:
                if idx.name == target:
                    break
            else:
                raise KeyError("no index named '%s'" % target)
            return idx.resolve_ref(self, env, fromdocname, builder, typ,
                            target, node, contnode)
        elif typ in self.directives:
            dir = self.directives[typ]
            return dir.resolve_ref(self, env, fromdocname, builder, typ,
                            target, node, contnode)


def setup(app):
    app.add_domain(BBDomain)
