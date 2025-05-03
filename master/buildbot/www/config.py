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


from __future__ import annotations

import json
import os
import typing
from typing import TYPE_CHECKING
from typing import Any

from twisted.internet import defer
from twisted.web.error import Error

from buildbot.interfaces import IConfigured
from buildbot.util import unicode2bytes
from buildbot.www import resource

if TYPE_CHECKING:
    from buildbot.master import BuildMaster


def get_environment_versions() -> list[tuple[str, str]]:
    import sys  # pylint: disable=import-outside-toplevel

    import twisted  # pylint: disable=import-outside-toplevel

    from buildbot import version as bbversion  # pylint: disable=import-outside-toplevel

    pyversion = '.'.join(map(str, sys.version_info[:3]))

    tx_version_info = (twisted.version.major, twisted.version.minor, twisted.version.micro)
    txversion = '.'.join(map(str, tx_version_info))

    return [
        ('Python', pyversion),
        ('Buildbot', bbversion),
        ('Twisted', txversion),
    ]


def get_www_frontend_config_dict(master: BuildMaster, www_config: dict[str, Any]) -> dict[str, Any]:
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
    config.pop('change_hook_dialects', None)

    # delete things that may contain information about the serving host
    config.pop('custom_templates_dir', None)

    return config


def serialize_www_frontend_config_dict_to_json(config: dict[str, Any]) -> str:
    def to_json(obj: Any) -> dict[str, Any] | str:
        obj = IConfigured(obj).getConfigDict()
        if isinstance(obj, dict):
            return obj
        # don't leak object memory address
        obj = obj.__class__.__module__ + "." + obj.__class__.__name__
        return repr(obj) + " not yet IConfigured"

    return json.dumps(config, default=to_json)


_known_theme_variables = (
    ("bb-sidebar-background-color", "#30426a"),
    ("bb-sidebar-header-background-color", "#273759"),
    ("bb-sidebar-header-text-color", "#fff"),
    ("bb-sidebar-title-text-color", "#627cb7"),
    ("bb-sidebar-footer-background-color", "#273759"),
    ("bb-sidebar-button-text-color", "#b2bfdc"),
    ("bb-sidebar-button-hover-background-color", "#1b263d"),
    ("bb-sidebar-button-hover-text-color", "#fff"),
    ("bb-sidebar-button-current-background-color", "#273759"),
    ("bb-sidebar-button-current-text-color", "#b2bfdc"),
    ("bb-sidebar-stripe-hover-color", "#e99d1a"),
    ("bb-sidebar-stripe-current-color", "#8c5e10"),
)


def serialize_www_frontend_theme_to_css(config: dict[str, Any], indent: int) -> str:
    theme_config = config.get('theme', {})

    return ('\n' + ' ' * indent).join([
        f'--{name}: {theme_config.get(name, default)};' for name, default in _known_theme_variables
    ])


def replace_placeholder_range(string: str, start: str, end: str, replacement: str) -> str:
    # Simple string replacement is much faster than a multiline regex
    i1 = string.find(start)
    i2 = string.find(end)
    if i1 < 0 or i2 < 0:
        return string
    return string[0:i1] + replacement + string[i2 + len(end) :]


class ConfigResource(resource.Resource):
    needsReconfig = True

    def reconfigResource(self, new_config: Any) -> None:
        self.frontend_config = get_www_frontend_config_dict(self.master, new_config.www)

    def render_GET(self, request: Any) -> int:
        return self.asyncRenderHelper(request, self.do_render)

    def do_render(self, request: Any) -> defer.Deferred:
        config: dict[str, Any] = {}
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

    def __init__(self, master: BuildMaster, staticdir: str) -> None:
        super().__init__(master)
        self.static_dir = staticdir
        with open(os.path.join(self.static_dir, 'index.html')) as index_f:
            self.index_template = index_f.read()

    def reconfigResource(self, new_config: Any) -> None:
        self.config = new_config.www
        self.frontend_config = get_www_frontend_config_dict(self.master, self.config)

    def render_GET(self, request: Any) -> int:
        return self.asyncRenderHelper(request, self.renderIndex)

    @defer.inlineCallbacks
    def renderIndex(self, request: Any) -> typing.Generator[Any, None, bytes]:
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
        serialized_css = serialize_www_frontend_theme_to_css(config, indent=8)
        rendered_index = self.index_template.replace(
            ' <!-- BUILDBOT_CONFIG_PLACEHOLDER -->',
            f"""<script id="bb-config">
    window.buildbotFrontendConfig = {serialized_config};
</script>""",
        )

        rendered_index = replace_placeholder_range(
            rendered_index,
            '<!-- BUILDBOT_THEME_CSS_PLACEHOLDER_BEGIN -->',
            '<!-- BUILDBOT_THEME_CSS_PLACEHOLDER_END -->',
            f"""<style>
      :root {{
        {serialized_css}
      }}
    </style>""",
        )

        return unicode2bytes(rendered_index, encoding='ascii')
