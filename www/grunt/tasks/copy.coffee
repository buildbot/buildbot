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
            dest: '.temp/scripts/libs'
            expand: true
            flatten: true
        ]

    # JavaScript test libraries
    libs_unit:
        files: [
            src: '<%= files.library.js_unit %>'
            dest: '.temp/scripts/test/libs'
            expand: true
            flatten: true
        ]

    # Fonts
    fonts:
        files: [
            src: '<%= files.fonts %>'
            dest: '.temp/fonts'
            expand: true
            flatten: true
        ]

    # Common files
    common:
        files: [
            src: '<%= files.common %>'
            dest: '.temp/common'
            expand: true
            flatten: true
        ]

    # JavaScript
    js:
        files: [
            src: '<%= files.js %>'
            dest: '.temp/scripts'
            expand: true
            flatten: true
        ]

    # JavaScript test
    js_unit:
        files: [
            src: '<%= files.js_unit %>'
            dest: '.temp/scripts/test'
            expand: true
            flatten: true
        ]

    # Images
    images:
        files: [
            src: '<%= files.images %>'
            dest: '.temp/img'
            expand: true
            flatten: true
        ]

    # Moving files from temp to build directory in development mode
    build_dev:
        files: [
            cwd: '.temp'
            src: '**'
            dest: '<%= dir.build %>'
            expand: true
        ]

    # Moving files from temp to build directory in production mode
    build_prod:
        files: [
            cwd: '.temp'
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
            src: '.temp/scripts/libs/require.js'
            dest: '<%= dir.build %>/scripts/require.js'
        ]