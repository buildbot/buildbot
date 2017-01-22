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

from __future__ import absolute_import
from __future__ import print_function

import json
import os
import posixpath

import jinja2

from twisted.internet import defer
from twisted.python import log
from twisted.web.error import Error

from buildbot.interfaces import IConfigured
from buildbot.www import resource


class IndexResource(resource.Resource):
    # enable reconfigResource calls
    needsReconfig = True

    def __init__(self, master, staticdir):
        resource.Resource.__init__(self, master)
        loader = jinja2.FileSystemLoader(staticdir)
        self.jinja = jinja2.Environment(
            loader=loader, undefined=jinja2.StrictUndefined)

    def reconfigResource(self, new_config):
        self.config = new_config.www

        versions = self.getEnvironmentVersions()
        vs = self.config.get('versions')
        if isinstance(vs, list):
            versions += vs
        self.config['versions'] = versions

        self.custom_templates = {}
        template_dir = self.config.pop('custom_templates_dir', None)
        if template_dir is not None:
            template_dir = os.path.join(self.master.basedir, template_dir)
            self.custom_templates = self.parseCustomTemplateDir(template_dir)

    def render_GET(self, request):
        return self.asyncRenderHelper(request, self.renderIndex)

    def parseCustomTemplateDir(self, template_dir):
        res = {}
        allowed_ext = [".html"]
        try:
            import pyjade
            allowed_ext.append(".jade")
        except ImportError:  # pragma: no cover
            log.msg("pyjade not installed. Ignoring .jade files from %s" %
                    (template_dir,))
            pyjade = None
        for root, dirs, files in os.walk(template_dir):
            if root == template_dir:
                template_name = posixpath.join("views", "%s.html")
            else:
                # template_name is a url, so we really want '/'
                # root is a os.path, though
                template_name = posixpath.join(
                    os.path.basename(root), "views", "%s.html")
            for f in files:
                fn = os.path.join(root, f)
                basename, ext = os.path.splitext(f)
                if ext not in allowed_ext:
                    continue
                if ext == ".html":
                    with open(fn) as f:
                        html = f.read().strip()
                elif ext == ".jade":
                    with open(fn) as f:
                        jade = f.read()
                        parser = pyjade.parser.Parser(jade)
                        block = parser.parse()
                        compiler = pyjade.ext.html.Compiler(
                            block, pretty=False)
                        html = compiler.compile()
                res[template_name % (basename,)] = json.dumps(html)
            pass
        return res

    @staticmethod
    def getEnvironmentVersions():
        import sys
        import twisted
        from buildbot import version as bbversion

        pyversion = '.'.join(map(str, sys.version_info[:3]))

        tx_version_info = (twisted.version.major,
                           twisted.version.minor,
                           twisted.version.micro)
        txversion = '.'.join(map(str, tx_version_info))

        return [
            ('Python', pyversion),
            ('Buildbot', bbversion),
            ('Twisted', txversion),
        ]

    @defer.inlineCallbacks
    def renderIndex(self, request):
        config = {}
        request.setHeader("content-type", 'text/html')
        request.setHeader("Cache-Control", "public;max-age=0")

        try:
            yield self.config['auth'].maybeAutoLogin(request)
        except Error as e:
            config["on_load_warning"] = e.message

        user_info = self.master.www.getUserInfos(request)
        config.update({"user": user_info})

        config.update(self.config)
        config['buildbotURL'] = self.master.config.buildbotURL
        config['title'] = self.master.config.title
        config['titleURL'] = self.master.config.titleURL
        config['multiMaster'] = self.master.config.multiMaster

        # delete things that may contain secrets
        if 'change_hook_dialects' in config:
            del config['change_hook_dialects']

        def toJson(obj):
            try:
                obj = IConfigured(obj).getConfigDict()
            except TypeError:
                # this happens for old style classes (not deriving objects)
                pass
            if isinstance(obj, dict):
                return obj
            # don't leak object memory address
            obj = obj.__class__.__module__ + "." + obj.__class__.__name__
            return repr(obj) + " not yet IConfigured"

        tpl = self.jinja.get_template('index.html')
        # we use Jinja in order to render some server side dynamic stuff
        # For example, custom_templates javascript is generated by the
        # layout.jade jinja template
        tpl = tpl.render(configjson=json.dumps(config, default=toJson),
                         custom_templates=self.custom_templates,
                         config=self.config)
        defer.returnValue(tpl.encode("ascii"))
