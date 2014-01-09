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

from twisted.web import resource


class Resource(resource.Resource):

    # if this is true for a class, then instances will have their
    # reconfigResource(new_config) methods called on reconfig.
    needsReconfig = False

    # as a convenience, subclasses have a ``master`` attribute, a
    # ``base_url`` attribute giving Buildbot's base URL,
    # and ``static_url`` attribute giving Buildbot's static files URL

    @property
    def base_url(self):
        return self.master.config.www['url']

    def __init__(self, master):
        resource.Resource.__init__(self)
        self.master = master
        if self.needsReconfig:
            master.www.resourceNeedsReconfigs(self)

    def reconfigResource(self, new_config):
        raise NotImplementedError


class RedirectResource(Resource):

    def __init__(self, master, basepath):
        Resource.__init__(self, master)
        self.basepath = basepath

    def render(self, request):
        redir = self.base_url + self.basepath
        request.redirect(redir)
        return redir
