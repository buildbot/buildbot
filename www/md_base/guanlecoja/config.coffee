### ###############################################################################################
#
#   This module contains all configuration for the build process
#
### ###############################################################################################
ANGULAR_TAG = "~1.3.15"
ANGULAR_MATERIAL_TAG = "~0.8.3"

path = require 'path'
gulp = require 'gulp'
shell = require("gulp-shell")
svgSymbols = require 'gulp-svg-symbols'

config =

    ### ###########################################################################################
    #   Directories
    ### ###########################################################################################
    dir:
        # The build folder is where the app resides once it's completely built
        build: 'buildbot_www/static'
        


    ### ###########################################################################################
    #   This is a collection of file patterns
    ### ###########################################################################################

    ### ###########################################################################################
    #   This is a collection of file patterns
    ### ###########################################################################################
    bower:
        # JavaScript libraries (order matters)
        deps:
            moment:
                version: "~2.6.0"
                files: 'moment.js'
            angular:
                version: ANGULAR_TAG
                files: 'angular.js'
            "angular-animate":
                version: ANGULAR_TAG
                files: 'angular-animate.js'
            "angular-aria":
                version: ANGULAR_TAG
                files: 'angular-aria.js'
            "angular-material":
                version: ANGULAR_MATERIAL_TAG
                files: 'angular-material.js'
            "angular-ui-router":
                version: '0.2.13'
                files: 'release/angular-ui-router.js'
            lodash:
                version: "~2.4.1"
                files: 'dist/lodash.js'
            'underscore.string':
                version: "~2.3.3"
                files: 'lib/underscore.string.js'
            # here we have the choice: ngSocket: no reconnecting, and not evolving since 10mon
            # reconnectingWebsocket implements reconnecting with expo backoff, but no good bower taging
            # reimplement reconnecting ourselves
            "reconnectingWebsocket":
                version: "master"
                files: ["reconnecting-websocket.js"]
            # TODO: Remove the dependency of restangular once the new
            # buildbotService is ready and restangular is deprecated
            restangular:
                version: "~1.4.0"
                files: 'dist/restangular.js'
                
        testdeps:
            "angular-mocks":
                version: "~1.3.15"
                files: "angular-mocks.js"

    buildtasks: ['scripts', 'styles', 'index', 'icons', 'tests', 'generatedfixtures', 'fixtures']

    generatedfixtures: ->
        gulp.src ""
            .pipe shell("buildbot dataspec -g window.dataspec -o " + path.join(config.dir.build,"generatedfixtures.js"))


gulp.task 'icons', ->
    gulp.src(['src/icons/*.svg', '!src/icons/iconset.svg'])
        .pipe(svgSymbols(
            title: false
            templates: ['src/icons/iconset.svg']
        ))
        .pipe(gulp.dest(path.join(config.dir.build, 'icons')))

gulp.task 'proxy', ->
    # this is a task for developing, it proxy api request to http://nine.buildbot.net
    argv = require('minimist')(process.argv)
    argv.host?= 'nine.buildbot.net'
    argv.port?= 8020

    fs = require 'fs'
    path = require 'path'
    http = require 'http'
    httpProxy = require 'http-proxy'
    proxy = httpProxy.createProxyServer({})
    proxy.on 'proxyReq', (proxyReq, req, res, options) ->
        delete proxyReq.removeHeader('Origin')
        delete proxyReq.removeHeader('Referer')
    proxy.on 'proxyRes', (proxyRes, req, res) ->
        proxyRes.headers['Access-Control-Allow-Origin'] = '*'
        console.log "[Proxy] #{req.method} #{req.url}"

    server = http.createServer (req, res) ->
        if req.url.match /^\/api/
            proxy.web req, res, {target: 'http://' + argv.host}
        else if req.url.match /^\/ws/
            proxy.ws req, res, {target: 'ws://' + argv.host}
    server.listen parseInt(argv.port)
    console.log "[Proxy] server listening on port #{argv.port}"

module.exports = config
