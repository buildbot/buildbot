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
# Portions copyright The Dojo Foundation

import os
import sys

def sibpath(*elts):
    return os.path.join(os.path.dirname(__file__), *elts)

## Dojo build profile

# This is the build profile.  It's a Python data structure, but its syntax and
# contents should be familiar to any Dojo hackers.  It is based on
# https://github.com/csnover/dojo-boilerplate/blob/master/profiles/app.profile.js
# incorporated here via the BSD license.

profile = {
    # `basePath` is relative to the directory containing this profile file; in
    # this case, it is being set to the src/ directory, which is the same place
    # as the `baseUrl` directory in the loader configuration. (If you change
    # this, you will also need to update run.js.)
    'basePath' : sibpath('src'),

    # Builds a new release.
    'action' : 'release',

    # Strips all comments and whitespace from CSS files and inlines @imports where possible.
    'cssOptimize' : 'comments',

    # Excludes tests, demos, and original template files from being included in the built version.
    'mini' : True,

    # Uses Closure Compiler as the JavaScript minifier. This can also be set to "shrinksafe" to use ShrinkSafe,
    # though ShrinkSafe is deprecated and not recommended.
    # This option defaults to "" (no compression) if not provided.
    'optimize' : 'closure',

    # We're building layers, so we need to set the minifier to use for those, too.
    # This defaults to "shrinksafe" if not provided.
    'layerOptimize' : 'closure',

    # Strips all calls to console functions within the code. You can also set this to "warn" to strip everything
    # but console.error, and any other truthy value to strip everything but console.warn and console.error.
    # This defaults to "normal" (strip all but warn and error) if not provided.
    'stripConsole' : 'all',

    # The default selector engine is not included by default in a dojo.js build
    # in order to make mobile builds smaller. We add it back here to avoid that
    # extra HTTP request. 
    'selectorEngine' : 'acme',

    # Builds can be split into multiple different JavaScript files called "layers". This allows applications to
    # defer loading large sections of code until they are actually required while still allowing multiple modules to
    # be compiled into a single file.
    'layers' : {
        'dojo/dojo': {
            'include' : [
                # basic dojo stuff
                'dojo/dojo', 'dojo/i18n', 'dojo/domReady',
                'dojox', 'dijit/dijit'
                ],
            'boot' : True,
            'customBase' : True
        },
        # everything else is loaded individually, for now
    },

    # Providing hints to the build system allows code to be conditionally removed on a more granular level than
    # simple module dependencies can allow. This is especially useful for creating tiny mobile builds.
    # Keep in mind that dead code removal only happens in minifiers that support it! Currently, only Closure Compiler
    # to the Dojo build system with dead code removal.
    # A documented list of has-flags in use within the toolkit can be found at
    # <http:#dojotoolkit.org/reference-guide/dojo/has.html>.
    'staticHasFeatures' : {
        # The trace & log APIs are used for debugging the loader, so we do not need them in the build.
        'dojo-trace-api': 0,
        'dojo-log-api': 0,

        # This causes normally private loader data to be exposed for debugging. In a release build, we do not need
        # that either.
        'dojo-publish-privates': 0,

        # This application is pure AMD, so get rid of the legacy loader.
        'dojo-sync-loader': 0,

        # `dojo-xhr-factory` relies on `dojo-sync-loader`, which we have removed.
        'dojo-xhr-factory': 0,

        # We are not loading tests in production, so we can get rid of some test sniffing code.
        'dojo-test-sniff': 0
    },

    'packages' : [
        # dojo core
        'dojo', 'dojox', 'dijit',
        # find doh in util
        { 'name': 'doh', 'location': 'util/doh' },
        # buildbot's code
        'bb',
        # extensions
        'dgrid',
        'put-selector',
        'xstyle',
        'moment'
    ],
}

# called from build.sh to get the contents of profile.js
def getProfile():
    import json
    return "var profile = %s;" % json.dumps(profile, indent=4)

# (see comments in setup.py about contexts)
#
# this script never runs in the SDIST state, so if src/ is missing,
# then we're INSTALLED
src_exists = os.path.isdir(sibpath('src'))
built_exists = os.path.isdir(sibpath('built'))
if src_exists:
    if not built_exists:
        context = 'SRC'
    else:
        context = 'BUILT'
else:
    context = 'INSTALLED'

class Application(object):
    def __init__(self):
        self.description = "Buildbot UI"

        # the rest depends on the context we're executing in
        if context == 'SRC':
            self.version = 'source'
            self.static_dir = os.path.abspath(sibpath('src'))
        elif context == 'BUILT':
            self.version = 'source'
            self.static_dir = os.path.abspath(sibpath('built'))
        else: # context == 'INSTALLED'
            instdir = os.path.join(sys.prefix, 'share', 'buildbot', 'built')
            verfile = os.path.join(instdir, 'buildbot-version.txt')
            self.version = open(verfile).read().strip()
            self.static_dir = instdir

        # as a sanity-check, ensure that the haml templates are built.  This
        # should only fail in SRC context, but it can't hurt to check
        # everywhere
        if not os.path.exists(os.path.join(self.static_dir,
                                    "bb", "ui", "templates", "home.haml.js")):
            raise ImportError("HAML files are not built; run ./build.sh --haml-only")

        self.packages = profile['packages']
        self.routes = [
            { 'path': "", 'name': "Home",
                'widget': "home"},
            { 'path': "overview", 'name': "Overview",
                'widget': "overview"},
            { 'path': "builders", 'name': "Builders",
                'widget': "builders"},
            { 'path': "builds", 'name': "Last Builds",
                'widget': "builds"},
            { 'path': "changes", 'name': "Last Changes",
                'widget': "changes"},
            { 'path': "slaves", 'name': "Build Slaves",
                'widget': "buildslaves"},
            { 'path': "masters", 'name': "Build Masters",
                'widget': "buildmasters"},
            { 'path': "users", 'name': "Users",
                'widget': "users"},
            { 'path': "admin", 'name': "Admin",
                'widget': "admin", 'enableif':['admin']},

            { 'path': "404", 'widget': "404"},

            # details paths
            { 'path': "builders/([^/]+)",
                'widget': "builder" },
            { 'path': "builders/([^/]+)/builds/([0-9]+)",
                'widget': "build" },
            { 'path': "builders/([^/]+)/builds/([0-9]+)/steps/([0-9]+)",
                'widget': "step" },
            { 'path': "builders/([^/]+)/builds/([0-9]+)/steps/([0-9]+)/logs/([^/]+)",
                'widget': "log" },
            { 'path': "slaves/([^/]+)",
                'widget': "buildslave"},
            { 'path': "masters/([^/]+)",
                'widget': "buildmaster"},
            { 'path': "users/([^/]+)",
                'widget': "user"}
        ]

# create the interface for the setuptools entry point
ep = Application()
