### ###############################################################################################
#
#   This module contains all configuration for the build process
#
### ###############################################################################################
ANGULAR_TAG = "~1.3.1"
gulp = require("gulp")
path = require("path")


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
                version: '~1.4.1'
                files: ['vendors.js', 'scripts.js']
            moment:
                version: "~2.6.0"
                files: 'moment.js'
            restangular:
                version: "~1.4.0"
                files: 'dist/restangular.js'
            d3:  # d3 is loaded on demand via d3Service
                version: "~3.4.11"
                files: []
            "font-awesome":
                version: "~4.1.0"
                files: []
            "bootstrap":
                version: "~3.1.1"
                files: []
            # here we have the choice: ngSocket: no reconnecting, and not evolving since 10mon
            # reconnectingWebsocket implements reconnecting with expo backoff, but no good bower taging
            # reimplement reconnecting ourselves
            "reconnectingWebsocket":
                version: "master"
                files: ["reconnecting-websocket.js"]
        testdeps:
            "angular-mocks":
                version: ANGULAR_TAG
                files: "angular-mocks.js"

    buildtasks: ['scripts', 'styles', 'fonts', 'imgs',
        'index', 'tests', 'fixtures', 'copyd3']

module.exports = config
