### ###############################################################################################
#
#   Copies directories and files from one location to another
#
### ###############################################################################################
module.exports =

    # JavaScript libraries
    libs:
        files: [
            src: '<%= files.library.js %>'
            dest: '<%= dir.temp %>/scripts/libs'
            expand: true
            flatten: true
        ]

    # JavaScript test libraries
    libs_unit:
        files: [
            src: '<%= files.library.js_unit %>'
            dest: '<%= dir.temp %>/scripts/test/libs'
            expand: true
            flatten: true
        ]

    # Fonts
    fonts:
        files: [
            src: '<%= files.fonts %>'
            dest: '<%= dir.temp %>/fonts'
            expand: true
            flatten: true
        ]

    # Common files
    common:
        files: [
            src: '<%= files.common %>'
            dest: '<%= dir.temp %>/common'
            expand: true
            flatten: true
        ]

    # JavaScript
    js:
        files: [
            src: '<%= files.js %>'
            dest: '<%= dir.temp %>/scripts'
            expand: true
            flatten: true
        ]

    # JavaScript test
    js_unit:
        files: [
            src: '<%= files.js_unit %>'
            dest: '<%= dir.temp %>/scripts/test'
            expand: true
            flatten: true
        ]

    # Images
    images:
        files: [
            src: '<%= files.images %>'
            dest: '<%= dir.temp %>/img'
            expand: true
            flatten: true
        ]

    # Moving files from temp to build directory in development mode
    build_dev:
        files: [
            cwd: '<%= dir.temp %>'
            src: '**'
            dest: '<%= dir.build %>'
            expand: true
        ]

    # Moving files from temp to build directory in production mode
    build_prod:
        files: [
            cwd: '<%= dir.temp %>'
            src: [
                'index.html'
                'scripts/main.js'
                'styles/**'
                'common/**'
                'img/**'
                'fonts/**'
            ]
            dest: '<%= dir.build %>'
            expand: true
        ,
            src: '<%= dir.temp %>/scripts/libs/require.js'
            dest: '<%= dir.build %>/scripts/require.js'
        ]