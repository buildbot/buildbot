### ###############################################################################################
#
#   Copies directories and files from one location to another
#
### ###############################################################################################
module.exports =

    # Copy compiled scripts
    js_compiled:
        files: [
            cwd: '<%= dir.temp %>/scripts'
            src: '**'
            dest: '<%= dir.temp %>/scripts/<%= name %>/scripts'
            expand: true
        ]

    # Moving files from temp to build directory in development mode
    plugin_dev:
        files: [
            cwd: '<%= dir.temp %>'
            src: ['**/*', '!scripts/**']
            dest: '<%= dir.build %>'
            expand: true
        ,
            cwd: '<%= dir.temp %>/scripts/<%= name %>'
            src: '**'
            dest: '<%= dir.build %>'
            expand: true
        ,
            cwd: '<%= dir.temp %>/scripts'
            src: 'main.js'
            dest: '<%= dir.build %>/scripts'
            expand: true
        ]