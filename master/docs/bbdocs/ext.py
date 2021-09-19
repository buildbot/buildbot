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
from docutils.parsers.rst import Directive
from sphinx import addnodes
from sphinx.domains import Domain
from sphinx.domains import Index
from sphinx.domains import ObjType
from sphinx.roles import XRefRole
from sphinx.util import logging
from sphinx.util import ws_re
from sphinx.util.docfields import DocFieldTransformer
from sphinx.util.docfields import Field
from sphinx.util.docfields import TypedField
from sphinx.util.nodes import make_refnode

logger = logging.getLogger(__name__)


class BBRefTargetDirective(Directive):

    """
    A directive that can be a target for references.  Attributes:

    @cvar ref_type: same as directive name
    @cvar indextemplates: templates for main index entries, if any
    """

    has_content = False
    name_annotation = None
    required_arguments = 1
    optional_arguments = 0
    final_argument_whitespace = True
    option_spec = {}
    domain = 'bb'
    doc_field_types = []

    def get_field_type_map(self):
        # This is the same as DocFieldTransformer.preprocess_fieldtype which got removed in
        # Sphinx 4.0
        typemap = {}
        for fieldtype in self.doc_field_types:
            for name in fieldtype.names:
                typemap[name] = fieldtype, False
            if fieldtype.is_typed:
                for name in fieldtype.typenames:
                    typemap[name] = fieldtype, True
        return typemap

    def run(self):
        self.env = env = self.state.document.settings.env
        # normalize whitespace in fullname like XRefRole does
        fullname = ws_re.sub(' ', self.arguments[0].strip())
        targetname = '{}-{}'.format(self.ref_type, fullname)

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
                indexentry = tpl[colon + 1:].strip() % (fullname,)
            else:
                indextype = 'single'
                indexentry = tpl % (fullname,)
            entries.append(
                (indextype, indexentry, targetname, targetname, None))

        if entries:
            inode = addnodes.index(entries=entries)
            ret.insert(0, inode)

        # if the node has content, set up a signature and parse the content
        if self.has_content:
            descnode = addnodes.desc()
            descnode['domain'] = 'bb'
            descnode['objtype'] = self.ref_type
            descnode['noindex'] = True
            signode = addnodes.desc_signature(fullname, '')

            if self.name_annotation:
                annotation = "{} ".format(self.name_annotation)
                signode += addnodes.desc_annotation(annotation, annotation)
            signode += addnodes.desc_name(fullname, fullname)
            descnode += signode

            contentnode = addnodes.desc_content()
            self.state.nested_parse(self.content, 0, contentnode)
            DocFieldTransformer(self).transform_all(contentnode)
            descnode += contentnode

            ret.append(descnode)

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
            logger.warning((f"{fromdocname}:{node.line}: "
                            f"Missing BB reference: bb:{cls.ref_type}:{target}"))
            return None

        return make_refnode(builder, fromdocname,
                            todocname, targetname,
                            contnode, target)


def make_ref_target_directive(ref_type, indextemplates=None, **kwargs):
    """
    Create and return a L{BBRefTargetDirective} subclass.
    """
    class_vars = dict(ref_type=ref_type, indextemplates=indextemplates)
    class_vars.update(kwargs)
    return type("BB{}RefTargetDirective".format(ref_type.capitalize()),
                (BBRefTargetDirective,), class_vars)


class BBIndex(Index):

    """
    A Buildbot-specific index.

    @cvar name: same name as the directive and xref role
    @cvar localname: name of the index document
    """

    def generate(self, docnames=None):
        content = {}
        idx_targets = self.domain.data['targets'].get(self.name, {})
        for name, (docname, targetname) in idx_targets.items():
            letter = name[0].upper()
            content.setdefault(letter, []).append(
                (name, 0, docname, targetname, '', '', ''))
        content = [(l, sorted(content[l], key=lambda tup: tup[0].lower()))
                   for l in sorted(content.keys())]
        return (content, False)

    @classmethod
    def resolve_ref(cls, domain, env, fromdocname, builder, typ, target, node,
                    contnode):
        """
        Resolve a reference to an index to the document containing the index,
        using the index's C{localname} as the content of the link.
        """
        # indexes appear to be automatically generated at doc DOMAIN-NAME
        todocname = "bb-{}".format(target)

        node = nodes.reference('', '', internal=True)
        node['refuri'] = builder.get_relative_uri(fromdocname, todocname)
        node['reftitle'] = cls.localname
        node.append(nodes.emphasis(cls.localname, cls.localname))
        return node


def make_index(name, localname):
    """
    Create and return a L{BBIndex} subclass, for use in the domain's C{indices}
    """
    return type("BB{}Index".format(name.capitalize()),
                (BBIndex,),
                dict(name=name, localname=localname))


class BBDomain(Domain):
    name = 'bb'
    label = 'Buildbot'

    object_types = {
        'cfg': ObjType('cfg', 'cfg'),
        'sched': ObjType('sched', 'sched'),
        'chsrc': ObjType('chsrc', 'chsrc'),
        'step': ObjType('step', 'step'),
        'reportgen': ObjType('reportgen', 'reportgen'),
        'reporter': ObjType('reporter', 'reporter'),
        'configurator': ObjType('configurator', 'configurator'),
        'worker': ObjType('worker', 'worker'),
        'cmdline': ObjType('cmdline', 'cmdline'),
        'msg': ObjType('msg', 'msg'),
        'event': ObjType('event', 'event'),
        'rtype': ObjType('rtype', 'rtype'),
        'rpath': ObjType('rpath', 'rpath'),
        'raction': ObjType('raction', 'raction'),
    }

    directives = {
        'cfg': make_ref_target_directive('cfg',
                                         indextemplates=[
                                             'single: Buildmaster Config; %s',
                                             'single: %s (Buildmaster Config)',
                                         ]),
        'sched': make_ref_target_directive('sched',
                                           indextemplates=[
                                               'single: Schedulers; %s',
                                               'single: %s Scheduler',
                                           ]),
        'chsrc': make_ref_target_directive('chsrc',
                                           indextemplates=[
                                               'single: Change Sources; %s',
                                               'single: %s Change Source',
                                           ]),
        'step': make_ref_target_directive('step',
                                          indextemplates=[
                                              'single: Build Steps; %s',
                                              'single: %s Build Step',
                                          ]),
        'reportgen': make_ref_target_directive('reportgen',
                                               indextemplates=[
                                                   'single: Report Generators; %s',
                                                   'single: %s Report Generator',
                                               ]),
        'reporter': make_ref_target_directive('reporter',
                                              indextemplates=[
                                                  'single: Reporter Targets; %s',
                                                  'single: %s Reporter Target',
                                              ]),
        'configurator': make_ref_target_directive('configurator',
                                              indextemplates=[
                                                  'single: Configurators; %s',
                                                  'single: %s Configurators',
                                              ]),
        'worker': make_ref_target_directive('worker',
                                            indextemplates=[
                                                'single: Build Workers; %s',
                                                'single: %s Build Worker',
                                            ]),
        'cmdline': make_ref_target_directive('cmdline',
                                             indextemplates=[
                                                 'single: Command Line Subcommands; %s',
                                                 'single: %s Command Line Subcommand',
                                             ]),
        'msg': make_ref_target_directive('msg',
                                         indextemplates=[
                                             'single: Message Schema; %s',
                                         ],
                                         has_content=True,
                                         name_annotation='routing key:',
                                         doc_field_types=[
                                             TypedField('key', label='Keys', names=('key',),
                                                        typenames=('type',), can_collapse=True),
                                             Field('var', label='Variable',
                                                   names=('var',)),
                                         ]),
        'event': make_ref_target_directive('event',
                                           indextemplates=[
                                               'single: event; %s',
                                           ],
                                           has_content=True,
                                           name_annotation='event:',
                                           doc_field_types=[
                                           ]),
        'rtype': make_ref_target_directive('rtype',
                                           indextemplates=[
                                               'single: Resource Type; %s',
                                           ],
                                           has_content=True,
                                           name_annotation='resource type:',
                                           doc_field_types=[
                                               TypedField('attr', label='Attributes',
                                                          names=('attr',),
                                                          typenames=('type',), can_collapse=True),
                                           ]),
        'rpath': make_ref_target_directive('rpath',
                                           indextemplates=[
                                               'single: Resource Path; %s',
                                           ],
                                           name_annotation='path:',
                                           has_content=True,
                                           doc_field_types=[
                                               TypedField('pathkey', label='Path Keys',
                                                          names=('pathkey',), typenames=('type',),
                                                          can_collapse=True),
                                           ]),
        'raction': make_ref_target_directive('raction',
                                             indextemplates=[
                                                 'single: Resource Action; %s',
                                             ],
                                             name_annotation='POST with method:',
                                             has_content=True,
                                             doc_field_types=[
                                                 TypedField('body', label='Body keys',
                                                            names=('body',), typenames=('type',),
                                                            can_collapse=True),
                                             ]),
    }

    roles = {
        'cfg': XRefRole(),
        'sched': XRefRole(),
        'chsrc': XRefRole(),
        'step': XRefRole(),
        'reportgen': XRefRole(),
        'reporter': XRefRole(),
        'configurator': XRefRole(),
        'worker': XRefRole(),
        'cmdline': XRefRole(),
        'msg': XRefRole(),
        'event': XRefRole(),
        'rtype': XRefRole(),
        'rpath': XRefRole(),
        'index': XRefRole()
    }

    initial_data = {
        'targets': {},  # type -> target -> (docname, targetname)
    }

    indices = [
        make_index("cfg", "Buildmaster Configuration Index"),
        make_index("sched", "Scheduler Index"),
        make_index("chsrc", "Change Source Index"),
        make_index("step", "Build Step Index"),
        make_index("reportgen", "Reporter Generator Index"),
        make_index("reporter", "Reporter Target Index"),
        make_index("configurator", "Configurator Target Index"),
        make_index("worker", "Build Worker Index"),
        make_index("cmdline", "Command Line Index"),
        make_index("msg", "MQ Routing Key Index"),
        make_index("event", "Data API Event Index"),
        make_index("rtype", "REST/Data API Resource Type Index"),
        make_index("rpath", "REST/Data API Path Index"),
        make_index("raction", "REST/Data API Actions Index"),
    ]

    def resolve_xref(self, env, fromdocname, builder, typ, target, node,
                     contnode):
        if typ == 'index':
            for idx in self.indices:
                if idx.name == target:
                    break
            else:
                raise KeyError("no index named '{}'".format(target))
            return idx.resolve_ref(self, env, fromdocname, builder, typ,
                                   target, node, contnode)
        elif typ in self.directives:
            dir = self.directives[typ]
            return dir.resolve_ref(self, env, fromdocname, builder, typ,
                                   target, node, contnode)

    def merge_domaindata(self, docnames, otherdata):
        for typ in self.object_types:
            if typ not in otherdata['targets']:
                continue

            if typ not in self.data['targets']:
                self.data['targets'][typ] = otherdata['targets'][typ]
                continue

            self_data = self.data['targets'][typ]
            other_data = otherdata['targets'][typ]

            for target_name, target_data in other_data.items():
                if target_name in self_data:
                    # for some reason we end up with multiple references to the same things in
                    # multiple domains. If both instances point to the same location, ignore it,
                    # otherwise issue a warning.
                    if other_data[target_name] == self_data[target_name]:
                        continue

                    self_path = '{0}#{1}'.format(self.env.doc2path(self_data[target_name][0]),
                                                 self_data[target_name][1])

                    other_path = '{0}#{1}'.format(self.env.doc2path(other_data[target_name][0]),
                                                  other_data[target_name][1])

                    logger.warning(('Duplicate index {} reference {} in {}, '
                                    'other instance in {}').format(typ, target_name,
                                                                   self_path, other_path))
                else:
                    self_data[target_name] = target_data


def setup(app):
    app.add_domain(BBDomain)
    return {'parallel_read_safe': True, 'parallel_write_safe': True}
