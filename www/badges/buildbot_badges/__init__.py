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

from klein import Klein
from twisted.internet import defer

from buildbot.data import resultspec
from buildbot.process.results import Results
from buildbot.www.plugin import Application


class Api(object):
    app = Klein()

    def __init__(self, ep):
        self.ep = ep

    @app.route("/<string:builder>/<string:size>", methods=['GET'])
    @defer.inlineCallbacks
    def getBuilder(self, request, builder, size):
        if size not in ("large", "normal", "small"):
            defer.returnValue("size: '{}' not in ('large', 'normal', 'small')".format(size))

        # get the last completed build for that builder using the data api
        last_build = yield self.ep.master.data.get(
            ("builders", builder, "builds"),
            limit=1, order=['-number'],
            filters=[resultspec.Filter('complete', 'eq', [True])])

        # get the status text corresponding to results code
        results_txt = "unknown"
        if last_build:
            results = last_build[0]['results']
            if results >= 0 and results < len(Results):
                results_txt = Results[results]

        # find the proper png file in our static dir
        fn = os.path.join(self.ep.static_dir, "{}_{}.png".format(results_txt, size))
        if os.path.exists(fn):
            with open(fn) as f:
                request.setHeader('Content-Type', 'image/png')
                defer.returnValue(f.read())

# create the interface for the setuptools entry point
ep = Application(__name__, "Buildbot badges", ui=False)
ep.resource = Api(ep).app.resource()
