### ###############################################################################################
#
#   This module contains all configuration for the build process
#
### ###############################################################################################
ANGULAR_TAG = "~1.3.0"
gulp = require("gulp")

gulp.task "copyace", ->
    gulp.src(["libs/ace-builds/src-noconflict/*.js", "!libs/ace-builds/src-noconflict/ace.js"])
        .pipe(gulp.dest(config.dir.build))


config =

    ### ###########################################################################################
    #   Name of the plugin
    ### ###########################################################################################
    name: 'codeparameter'


    ### ###########################################################################################
    #   Directories
    ### ###########################################################################################
    dir:
        # The build folder is where the app resides once it's completely built
        build: 'buildbot_codeparameter/static'

    ### ###########################################################################################
    #   Bower dependancies configuration
    ### ###########################################################################################
    bower:
        deps:
            "ace-builds":
                version: '1.1.5'
                files: 'src-noconflict/ace.js'
            "angular-ui-ace":
                version: '0.1.1'
                files: 'ui-ace.js'
        testdeps:
            jquery:
                version: '2.1.1'
                files: 'dist/jquery.js'
            angular:
                version: ANGULAR_TAG
                files: 'angular.js'
            lodash:
                version: "~2.4.1"
                files: 'dist/lodash.js'
            "angular-mocks":
                version: ANGULAR_TAG
                files: "angular-mocks.js"

    buildtasks: ['scripts', 'styles', 'fonts', 'imgs',
        'index', 'tests', 'generatedfixtures', 'fixtures', 'copyace']

    karma:
        # we put tests first, so that we have angular, and fake app defined
        files: ["tests.js", "scripts.js", 'fixtures.js', "mode-python.js"]
module.exports = config
