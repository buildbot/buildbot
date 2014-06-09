### ###############################################################################################
#
#   Watch file changes
#   Using grunt newer to run tasks with changed files only
#
### ###############################################################################################
module.exports =

    configFiles:
        files: [
            'Gruntfile.coffee'
            'grunt/config.coffee'
            'grunt/tasks/*.coffee'
        ]
        options:
            reload: true

    coffee:
        files: '<%= files.coffee %>'
        tasks: [
            'newer:coffee:compile'
            'requiregen'
            'newer:copy:build_dev'
            'karma:unit:run'
        ]

    coffee_unit:
        files: '<%= files.coffee_unit %>'
        tasks: [
            'newer:coffee:unit'
            'requiregen'
            'newer:copy:build_dev'
            'karma:unit:run'
        ]

    jade:
        files: [
            '<%= files.templates %>'
            '<%= files.index %>'
        ]
        tasks: [
            'newer:jade:compile'
            'newer:copy:build_dev'
        ]

    less:
        files: '<%= files.less %>'
        tasks: [
            'newer:less:compile'
            'newer:copy:build_dev'
        ]

    options:
        livereload: true