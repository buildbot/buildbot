/*
 * decaffeinate suggestions:
 * DS102: Remove unnecessary code created because of implicit returns
 * DS207: Consider shorter variations of null checks
 * Full docs: https://github.com/decaffeinate/decaffeinate/blob/master/docs/suggestions.md
 */
/* *///###########################################################################################
//
//   This module contains all configuration for the build process
//
/* *///###########################################################################################
const ANGULAR_TAG = "~1.5.3";
const gulp = require("gulp");
let path = require("path");
const shell = require("gulp-shell");


// d3 is loaded on demand, so it is just copied in the static dir
gulp.task("copyd3", () =>
    gulp.src(["libs/d3/d3.min.js"])
        .pipe(gulp.dest(config.dir.build))
);

var config = {

    /* *///#######################################################################################
    //   Directories
    /* *///#######################################################################################
    dir: {
        // The build folder is where the app resides once it's completely built
        build: 'buildbot_www/static'
    },
    files: {
        images: [
            'src/**/*.{png,jpg,gif,ico,svg}'
        ]
    },
    /* *///#######################################################################################
    //   Bower dependencies configuration
    /* *///#######################################################################################
    bower: {
        // JavaScript libraries (order matters)
        deps: {
            "guanlecoja-ui": {
                version: '~2.0.0',
                files: ['vendors.js', 'scripts.js']
            },
            moment: {
                version: "~2.6.0",
                files: 'moment.js'
            },
            d3: {  // d3 is loaded on demand via d3Service
                version: "~3.4.11",
                files: []
            },
            "font-awesome": {
                version: "~4.1.0",
                files: [],
                files: []
            },
            "bootstrap": {
                version: "~3.1.1",
                files: []
            },
            'buildbot-data': {
                version: '~2.2.6',
                files: 'dist/buildbot-data.js'
            },
            "angular-bootstrap-multiselect": {
                version: "https://github.com/bentorfs/angular-bootstrap-multiselect.git#^1.1.6",
                files: 'dist/angular-bootstrap-multiselect.js'
            }
        },

        testdeps: {
            "angular-mocks": {
                version: ANGULAR_TAG,
                files: "angular-mocks.js"
            }
        }
    },

    buildtasks: ['scripts', 'styles', 'fonts', 'imgs',
        'index', 'tests', 'fixtures', 'copyd3']
};

gulp.task('processindex', ['index'], function() {
    const indexpath = path.join(config.dir.build, 'index.html');
    return gulp.src("")
        .pipe(shell(`buildbot processwwwindex -i \"${indexpath}\"`));
});

gulp.task('proxy', ['processindex'], function() {
    // this is a task for developing, it proxy api request to http://nine.buildbot.net
    const argv = require('minimist')(process.argv);
    if (argv.host == null) {argv.host = 'nine.buildbot.net'; }
    if (argv.port == null) {argv.port = 8080; }
    if (argv.secure == null) {argv.secure = false; }
    if (argv.ignoresslerrors == null) {argv.ignoresslerrors = false; }

    const fs = require('fs');
    path = require('path');
    const http = require('http');
    const httpProxy = require('http-proxy');
    const proxy = httpProxy.createProxyServer({
        secure: !argv.ignoresslerrors,
    });
    proxy.on('proxyReq', function(proxyReq, req, res, options) {
        delete proxyReq.removeHeader('Origin');
        return delete proxyReq.removeHeader('Referer');
    });
    proxy.on('proxyRes', function(proxyRes, req, res) {
        proxyRes.headers['Access-Control-Allow-Origin'] = '*';
        return console.log(`[Proxy] ${req.method} ${req.url}`);
    });

    const server = http.createServer(function(req, res) {
        if (req.url.match(/^\/(api|sse|avatar)/)) {
            return proxy.web(req, res, {target: `http${argv.secure ? 's' : ''}://${argv.host}`});
        } else {
            let filepath = config.dir.build + req.url.split('?')[0];
            if (fs.existsSync(filepath) && fs.lstatSync(filepath).isDirectory()) {
                filepath = path.join(filepath, 'index.html');
            }
            return fs.readFile(filepath, function(err, data) {
                if (err) {
                    res.writeHead(404);
                    return res.end(JSON.stringify(err));
                } else {
                    res.writeHead(200);
                    return res.end(data);
                }
            });
        }
    });
    server.on('upgrade',  (req, socket, head) => proxy.ws(req, socket, {target: `ws${argv.secure ? 's' : ''}://${argv.host}`}));

    server.listen(parseInt(argv.port));
    return console.log(`[Proxy] server listening on port ${argv.port}, target {http${argv.secure ? 's' : ''},ws${argv.secure ? 's' : ''}}://${argv.host}/{api,sse,avatar}`);
});

module.exports = config;
