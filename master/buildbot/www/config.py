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


import json
import os
import posixpath

import jinja2

from twisted.internet import defer
from twisted.python import log
from twisted.web.error import Error

from buildbot.interfaces import IConfigured
from buildbot.util import unicode2bytes
from buildbot.www import resource


def get_environment_versions():
    import sys   # pylint: disable=import-outside-toplevel
    import twisted   # pylint: disable=import-outside-toplevel
    from buildbot import version as bbversion   # pylint: disable=import-outside-toplevel

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


def get_www_frontend_config_dict(master, www_config):
    # This config is shared with the frontend.
    config = dict(www_config)

    versions = get_environment_versions()
    vs = config.get('versions')
    if isinstance(vs, list):
        versions += vs
    config['versions'] = versions

    config['buildbotURL'] = master.config.buildbotURL
    config['title'] = master.config.title
    config['titleURL'] = master.config.titleURL
    config['multiMaster'] = master.config.multiMaster

    # delete things that may contain secrets
    if 'change_hook_dialects' in config:
        del config['change_hook_dialects']

    # delete things that may contain information about the serving host
    if 'custom_templates_dir' in config:
        del config['custom_templates_dir']

    return config


def serialize_www_frontend_config_dict_to_json(config):

    def to_json(obj):
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

    return json.dumps(config, default=to_json)


class ConfigResource(resource.Resource):
    needsReconfig = True

    def reconfigResource(self, new_config):
        self.frontend_config = get_www_frontend_config_dict(self.master, new_config.www)

    def render_GET(self, request):
        return self.asyncRenderHelper(request, self.do_render)

    def do_render(self, request):
        config = {}
        request.setHeader(b"content-type", b'application/json')
        request.setHeader(b"Cache-Control", b"public,max-age=0")

        config.update(self.frontend_config)
        config.update({"user": self.master.www.getUserInfos(request)})

        return defer.succeed(
            unicode2bytes(serialize_www_frontend_config_dict_to_json(config), encoding='ascii')
        )


class IndexResource(resource.Resource):
    # enable reconfigResource calls
    needsReconfig = True

    def __init__(self, master, staticdir):
        super().__init__(master)
        loader = jinja2.FileSystemLoader(staticdir)
        self.jinja = jinja2.Environment(
            loader=loader, undefined=jinja2.StrictUndefined)

    def reconfigResource(self, new_config):
        self.config = new_config.www
        self.frontend_config = get_www_frontend_config_dict(self.master, self.config)

        self.custom_templates = {}
        template_dir = self.config.get('custom_templates_dir', None)
        if template_dir is not None:
            template_dir = os.path.join(self.master.basedir, template_dir)
            self.custom_templates = self.parseCustomTemplateDir(template_dir)

    def render_GET(self, request):
        return self.asyncRenderHelper(request, self.renderIndex)

    def parseCustomTemplateDir(self, template_dir):
        res = {}
        allowed_ext = [".html"]
        try:
            import pypugjs  # pylint: disable=import-outside-toplevel
            allowed_ext.append(".jade")
        except ImportError:  # pragma: no cover
            log.msg(f"pypugjs not installed. Ignoring .jade files from {template_dir}")
            pypugjs = None
        for root, _, files in os.walk(template_dir):
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
                    with open(fn, encoding='utf-8') as f:
                        html = f.read().strip()
                elif ext == ".jade":
                    with open(fn, encoding='utf-8') as f:
                        jade = f.read()
                        parser = pypugjs.parser.Parser(jade)
                        block = parser.parse()
                        compiler = pypugjs.ext.html.Compiler(
                            block, pretty=False)
                        html = compiler.compile()
                res[template_name % (basename,)] = html

        return res

    @defer.inlineCallbacks
    def renderIndex(self, request):
        config = {}
        request.setHeader(b"content-type", b'text/html')
        request.setHeader(b"Cache-Control", b"public,max-age=0")

        try:
            yield self.config['auth'].maybeAutoLogin(request)
        except Error as e:
            config["on_load_warning"] = e.message

        config.update(self.frontend_config)
        config.update({"user": self.master.www.getUserInfos(request)})

        tpl = self.jinja.get_template('index.html')
        # we use Jinja in order to render some server side dynamic stuff
        # For example, custom_templates javascript is generated by the
        # layout.jade jinja template
        tpl = tpl.render(configjson=serialize_www_frontend_config_dict_to_json(config),
                         custom_templates=self.custom_templates,
                         config=self.config)
        return unicode2bytes(tpl, encoding='ascii')


class IndexResourceReact(resource.Resource):
    # enable reconfigResource calls
    needsReconfig = True

    def __init__(self, master, staticdir):
        super().__init__(master)
        self.static_dir = staticdir
        with open(os.path.join(self.static_dir, 'index.html')) as index_f:
            self.index_template = index_f.read()

    def reconfigResource(self, new_config):
        self.config = new_config.www
        self.frontend_config = get_www_frontend_config_dict(self.master, self.config)

    def render_GET(self, request):
        return self.asyncRenderHelper(request, self.renderIndex)

    @defer.inlineCallbacks
    def renderIndex(self, request):
        config = {}
        request.setHeader(b"content-type", b'text/html')
        request.setHeader(b"Cache-Control", b"public,max-age=0")

        try:
            yield self.config['auth'].maybeAutoLogin(request)
        except Error as e:
            config["on_load_warning"] = e.message

        config.update(self.frontend_config)
        config.update({"user": self.master.www.getUserInfos(request)})

        serialized_config = serialize_www_frontend_config_dict_to_json(config)
        rendered_index = self.index_template.replace(
            ' <!-- BUILDBOT_CONFIG_PLACEHOLDER -->',
            f'''<script id="bb-config">
    window.buildbotFrontendConfig = {serialized_config};
</script>'''
        )

        return unicode2bytes(rendered_index, encoding='ascii')
