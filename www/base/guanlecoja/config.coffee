### ###############################################################################################
#
#   This module contains all configuration for the build process
#
### ###############################################################################################
ANGULAR_TAG = "~1.4.6"
gulp = require("gulp")
path = require("path")
shell = require("gulp-shell")


# d3 is loaded on demand, so it is just copied in the static dir
gulp.task "copyd3", ->
    gulp.src(["libs/d3/d3.min.js"])
        .pipe(gulp.dest(config.dir.build))

config =

    ### ###########################################################################################
    #   Directories
    ### ###########################################################################################
    dir:
        # The build folder is where the app resides once it's completely built
        build: 'buildbot_www/static'

    ### ###########################################################################################
    #   Bower dependancies configuration
    ### ###########################################################################################
    bower:
        # JavaScript libraries (order matters)
        deps:
            "guanlecoja-ui":
                version: '~1.5.0'
                files: ['vendors.js', 'scripts.js']
            moment:
                version: "~2.6.0"
                files: 'moment.js'
            d3:  # d3 is loaded on demand via d3Service
                version: "~3.4.11"
                files: []
            "font-awesome":
                version: "~4.1.0"
                files: []
            "bootstrap":
                version: "~3.1.1"
                files: []
            'buildbot-data':
                version: '~1.1.0'
                files: 'dist/buildbot-data.js'

        testdeps:
            "angular-mocks":
                version: ANGULAR_TAG
                files: "angular-mocks.js"

    buildtasks: ['scripts', 'styles', 'fonts', 'imgs',
        'index', 'tests', 'fixtures', 'copyd3']

gulp.task 'processindex', ['index'], ->
    indexpath = path.join(config.dir.build, 'index.html')
    gulp.src ""
        .pipe shell("buildbot processwwwindex -i '#{indexpath}'")

gulp.task 'proxy', ['processindex'], ->
    # this is a task for developing, it proxy api request to http://nine.buildbot.net
    argv = require('minimist')(process.argv)
    argv.host?= 'nine.buildbot.net'
    argv.port?= 8080

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
        if req.url.match /^\/(api|sse|avatar)/
            proxy.web req, res, {target: 'http://' + argv.host}
        else
            filepath = config.dir.build + req.url.split('?')[0]
            if fs.existsSync(filepath) and fs.lstatSync(filepath).isDirectory()
                filepath = path.join(filepath, 'index.html')
            fs.readFile filepath, (err, data) ->
                if err
                    res.writeHead(404)
                    res.end(JSON.stringify(err))
                else
                    res.writeHead(200)
                    res.end(data)
    server.on 'upgrade',  (req, socket, head) ->
        proxy.ws req, socket, {target: 'ws://' + argv.host}

    server.listen parseInt(argv.port)
    console.log "[Proxy] server listening on port #{argv.port}"

module.exports = config
