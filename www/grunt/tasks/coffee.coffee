### ###############################################################################################
#
#   Compile CoffeeScript files to JavaScript
#
### ###############################################################################################
module.exports =

    options:
        sourceMap: true

    compile:
        files: [
            src: '<%= files.coffee %>'
            dest: '.temp/scripts'
            expand: true
            flatten: true
            extDot: 'last'
            ext: '.js'
        ]

    unit:
        files: [
            src: '<%= files.coffee_unit %>'
            dest: '.temp/scripts/test'
            expand: true
            flatten: true
            extDot: 'last'
            ext: '.js'
        ]