### ###############################################################################################
#
#   Build configurations:
#   - loading Grunt plugins and tasks
#   - custom tasks
#
### ###############################################################################################
module.exports = (grunt) ->

    # Load Node.js path module
    path = require('path')

    # Load in the build config file
    buildConfig = require('./grunt/config.coffee')

    # Load grunt tasks and configuration automatically
    options =
        configPath: path.join(process.cwd(), '../grunt/tasks')
        data:
            config: buildConfig
    taskConfig = require('load-grunt-config')(grunt, options)

    # Load grunt tasks and configuration automatically
    options =
        configPath: path.join(process.cwd(), 'grunt/tasks')
        data:
            config: buildConfig
    pluginTaskConfig = require('load-grunt-config')(grunt, options)

    # Merge the configs
    grunt.config.merge(buildConfig)
    grunt.config.merge(taskConfig)
    grunt.config.merge(pluginTaskConfig)

    ### ###########################################################################################
    #   Alias tasks
    ### ###########################################################################################

    # Compiles all files, then set up a watcher to build whenever files change
    grunt.registerTask 'dev', [
        'default'
        'karma:unit'
        'watch'
    ]

    # Building for the production environment
    grunt.registerTask 'prod', [
        'clean'
        'concurrent:compile_prod'
        'concurrent:copy_prod'
        'concat:bower_config'
        'ngtemplates'
        'requiregen'
        'requirejs'
        'copy:build_prod'
    ]

    # Steps needed for CI
    grunt.registerTask 'ci', [
        'default'
        'karma:ci'
    ]

    # Default task
    grunt.registerTask 'default', [
        'clean'
        'concurrent:compile_dev'
        'concurrent:copy_dev'
        'concat:bower_config'
        'copy:js_compiled'
        'clean:scripts'
        'requiregen'
        'copy:plugin_dev'
    ]