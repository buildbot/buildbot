### ###############################################################################################
#
#   This module contains all configuration for the build process
#
### ###############################################################################################
ANGULAR_TAG = "~1.2.17"
gulp = require("gulp")
shell = require("gulp-shell")
path = require("path")


# d3 is loaded on demand, so it is just copied in the static dir
gulp.task "copyd3", ->
    gulp.src(["libs/d3/d3.min.js"])
        .pipe(gulp.dest("static"))

config =

    ### ###########################################################################################
    #   Directories
    ### ###########################################################################################
    dir:
        # The build folder is where the app resides once it's completely built
        build: 'static'

    ### ###########################################################################################
    #   Bower dependancies configuration
    ### ###########################################################################################
    bower:
        # JavaScript libraries (order matters)
        deps:
            jquery:
                version: '~2.1.1'
                files: 'dist/jquery.js'
            angular:
                version: ANGULAR_TAG
                files: 'angular.js'
            "angular-animate":
                version: ANGULAR_TAG
                files: 'angular-animate.js'
            "angular-bootstrap":
                version: '~0.11.0'
                files: 'ui-bootstrap-tpls.js'
            "angular-ui-router":
                version: '~0.2.10'
                files: 'release/angular-ui-router.js'
            "angular-recursion":
                version: '~1.0.1'
                files: 'angular-recursion.js'
            lodash:
                version: "~2.4.1"
                files: 'dist/lodash.js'
            moment:
                version: "~2.6.0"
                files: 'moment.js'
            'underscore.string':
                version: "~2.3.3"
                files: 'lib/underscore.string.js'
            restangular:
                version: "~1.4.0"
                files: 'dist/restangular.js'
            d3:  # d3 is loaded on demand via d3Service
                version: "~3.4.11"
                files: []
        testdeps:
            "angular-mocks":
                version: ANGULAR_TAG
                files: "angular-mocks.js"

    buildtasks: ['scripts', 'styles', 'fonts', 'imgs',
        'index', 'tests', 'generatedfixtures', 'fixtures', 'copyd3']

    generatedfixtures: ->
        gulp.src ""
            .pipe shell("buildbot dataspec -g window.dataspec -o " + path.join(config.dir.build,"generatedfixtures.js"))

module.exports = config
