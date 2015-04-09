### ###############################################################################################
#
#   This module contains all configuration for the build process
#
### ###############################################################################################
ANGULAR_TAG = "~1.3.15"
ANGULAR_MATERIAL_TAG = "~0.8.3"

path = require 'path'
gulp = require 'gulp'
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
        testdeps:
            "angular-mocks":
                version: "~1.3.15"
                files: "angular-mocks.js"

    buildtasks: ['scripts', 'styles', 'index', 'icons', 'tests']


gulp.task 'icons', ->
    gulp.src(['src/icons/*.svg', '!src/icons/iconset.svg'])
        .pipe(svgSymbols(
            title: false
            templates: ['src/icons/iconset.svg']
        ))
        .pipe(gulp.dest(path.join(config.dir.build, 'icons')))

module.exports = config
