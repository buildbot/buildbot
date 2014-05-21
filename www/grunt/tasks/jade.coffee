### ###############################################################################################
#
#   Compile Jade files to HTML
#
### ###############################################################################################
module.exports =

    # Development mode
    dev:
        files: [
            src: '<%= files.templates %>'
            dest: '<%= dir.temp %>/views'
            expand: true
            flatten: true
            ext: '.html'
        ,
            src: '<%= files.index %>'
            dest: '<%= dir.temp %>/index.html'
        ]
        options:
            # Output indented HTML
            pretty: true
            data:
                # Set the environment to development
                environment: 'dev'

    # Production mode
    prod:
        files: [
            src: '<%= files.templates %>'
            dest: '<%= dir.temp %>/views'
            expand: true
            flatten: true
            ext: '.html'
        ,
            src: '<%= files.index %>'
            dest: '<%= dir.temp %>/index.html'
        ]
        options:
            data:
                # Set the environment to production
                environment: 'prod'