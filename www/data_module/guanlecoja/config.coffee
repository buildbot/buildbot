### ###############################################################################################
#
#   This module contains all configuration for the build process
#
### ###############################################################################################
ANGULAR_TAG = '~1.4.1'

gulp = require('gulp')

gulp.task 'readme', ->
    gulp.src('Readme.md').pipe gulp.dest(config.dir.build)

config =

    ### ###########################################################################################
    #   Name of the module
    ### ###########################################################################################
    name: 'bbData'

    ### ###########################################################################################
    #   Directories
    ### ###########################################################################################
    dir:
        # The build folder is where the app resides once it's completely built
        build: 'dist'

    sourcemaps: true
    vendors_apart: true
    ### ###########################################################################################
    #   Bower dependancies configuration
    ### ###########################################################################################
    bower:
        deps:
            angular:
                version: ANGULAR_TAG
                files: 'angular.js'
            tabex:
                version: '~1.0.3'
                files: 'dist/tabex.js'
            dexie:
                version: '~1.1.0'
                files: 'dist/latest/Dexie.js'
        testdeps:
            'angular-mocks':
                version: ANGULAR_TAG
                files: 'angular-mocks.js'

    ngclassify: (config) ->
        return {
            appName: config.name
            provider:
              suffix: 'Service'
        }

    buildtasks: ['scripts', 'vendors', 'tests', 'readme']

module.exports = config
