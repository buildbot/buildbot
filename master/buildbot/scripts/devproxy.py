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


import asyncio
import json
import logging

import aiohttp  # dev-proxy command requires aiohttp! run 'pip install aiohttp'
import aiohttp.web
import jinja2

from buildbot.plugins.db import get_plugins

log = logging.getLogger(__name__)


class DevProxy:
    MAX_CONNECTIONS = 10

    def __init__(self, port, next_url, plugins, unsafe_ssl, auth_cookie):
        while next_url.endswith('/'):
            next_url = next_url[:-1]
        self.next_url = next_url
        self.app = app = aiohttp.web.Application()
        self.apps = get_plugins('www', None, load_now=True)
        self.unsafe_ssl = unsafe_ssl
        cookies = {}
        if auth_cookie:
            if "TWISTED_SESSION" in auth_cookie:  # user pasted the whole document.cookie part!
                cookies = dict(c.split("=") for c in auth_cookie.split(";"))
                auth_cookie = cookies["TWISTED_SESSION"]
            cookies = {'TWISTED_SESSION': auth_cookie}
        logging.basicConfig(level=logging.DEBUG)
        if plugins is None:
            plugins = {}
        else:
            plugins = json.loads(plugins)

        self.plugins = plugins

        app.router.add_route('*', '/ws', self.ws_handler)
        for path in ['/api', '/auth', '/sse', '/avatar']:
            app.router.add_route('*', path + '{path:.*}', self.proxy_handler)
        app.router.add_route('*', '/', self.index_handler)
        for plugin in self.apps.names:
            if plugin != 'base':
                staticdir = self.apps.get(plugin).static_dir
                app.router.add_static('/' + plugin, staticdir)
        staticdir = self.staticdir = self.apps.get('base').static_dir
        loader = jinja2.FileSystemLoader(staticdir)
        self.jinja = jinja2.Environment(
            loader=loader, undefined=jinja2.StrictUndefined)
        app.router.add_static('/', staticdir)
        conn = aiohttp.TCPConnector(
            limit=self.MAX_CONNECTIONS, verify_ssl=(not self.unsafe_ssl))
        self.session = aiohttp.ClientSession(connector=conn, trust_env=True, cookies=cookies)
        self.config = None
        self.buildbotURL = f"http://localhost:{port}/"
        app.on_startup.append(self.on_startup)
        app.on_cleanup.append(self.on_cleanup)
        aiohttp.web.run_app(app, host="localhost", port=port)

    async def on_startup(self, app):
        try:
            await self.fetch_config_from_upstream()
        except aiohttp.ClientConnectionError as e:
            raise RuntimeError("Unable to connect to buildbot master" + str(e)) from e

    async def on_cleanup(self, app):
        await self.session.close()

    async def ws_handler(self, req):
        # based on https://github.com/oetiker/aio-reverse-proxy/blob/master/paraview-proxy.py
        ws_server = aiohttp.web.WebSocketResponse()
        await ws_server.prepare(req)

        async with self.session.ws_connect(
            self.next_url + "/ws", headers=req.headers
        ) as ws_client:

            async def ws_forward(ws_from, ws_to):
                async for msg in ws_from:
                    if ws_to.closed:
                        await ws_to.close(code=ws_to.close_code, message=msg.extra)
                        return
                    if msg.type == aiohttp.WSMsgType.TEXT:
                        await ws_to.send_str(msg.data)
                    elif msg.type == aiohttp.WSMsgType.BINARY:
                        await ws_to.send_bytes(msg.data)
                    elif msg.type == aiohttp.WSMsgType.PING:
                        await ws_to.ping()
                    elif msg.type == aiohttp.WSMsgType.PONG:
                        await ws_to.pong()
                    else:
                        raise ValueError(f'unexpected message type: {msg}')

            # keep forwarding websocket data in both directions
            await asyncio.wait(
                [
                    ws_forward(ws_server, ws_client),
                    ws_forward(ws_client, ws_server)
                ],
                return_when=asyncio.FIRST_COMPLETED)
        return ws_server

    async def proxy_handler(self, req):
        method = getattr(self.session, req.method.lower())
        upstream_url = self.next_url + req.path
        headers = req.headers.copy()
        query = req.query
        try:
            # note that req.content is a StreamReader, so the data is streamed
            # and not fully loaded in memory (unlike with python-requests)
            async with method(upstream_url,
                              headers=headers,
                              params=query,
                              allow_redirects=False,
                              data=req.content) as request:
                response = aiohttp.web.StreamResponse(
                    status=request.status, headers=request.headers)
                writer = await response.prepare(req)
                while True:
                    chunk = await request.content.readany()
                    if not chunk:
                        break
                    # using writer.write instead of response.write saves a few checks
                    await writer.write(chunk)
                return response
        except aiohttp.ClientConnectionError as e:
            return self.connection_error(e)

    def connection_error(self, error):
        return aiohttp.web.Response(text=f'Unable to connect to upstream server {self.next_url} '
                                         f'({error!s})', status=502)

    async def fetch_config_from_upstream(self):
        async with self.session.get(self.next_url) as request:
            index = await request.content.read()
            if request.status != 200:
                raise RuntimeError("Unable to fetch buildbot config: " + index.decode())
        # hack to parse the configjson from upstream buildbot config
        start_delimiter = b'angular.module("buildbot_config", []).constant("config", '
        start_index = index.index(start_delimiter)
        last_index = index.index(b')</script></html>')
        self.config = json.loads(
            index[start_index + len(start_delimiter):last_index].decode())

        # keep the original config, but remove the plugins that we don't know
        for plugin in list(self.config['plugins'].keys()):
            if plugin not in self.apps:
                del self.config['plugins'][plugin]
                log.warn("warning: Missing plugin compared to original buildbot: %s", plugin)

        # add the plugins configs passed in cmdline
        for k, v in self.plugins.items():
            self.config['plugins'][k] = v

        self.config['buildbotURL'] = self.buildbotURL
        self.config['buildbotURLs'] = [self.buildbotURL, self.next_url + "/"]

    async def index_handler(self, req):
        tpl = self.jinja.get_template('index.html')
        index = tpl.render(configjson=json.dumps(self.config),
                           custom_templates={},
                           config=self.config)
        return aiohttp.web.Response(body=index, content_type='text/html')


def devproxy(config):
    DevProxy(config['port'], config['buildbot_url'],
             config['plugins'], config['unsafe_ssl'], config['auth_cookie'])
