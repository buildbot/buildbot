### ###############################################################################################
#
#   Run tasks concurrently
#   Compiles and copies files in parallel
#
### ###############################################################################################
module.exports =

    compile_dev: [
        'coffeelint'
        'coffee'
        'jade:dev'
        'less:dev'
    ]

    copy_dev: [
        'copy:libs'
        'copy:libs_unit'
        'copy:fonts'
        'copy:common'
        'copy:js'
        'copy:js_unit'
        'copy:images'
    ]

    compile_prod: [
        'coffeelint'
        'coffee:compile'
        'jade:prod'
        'less:prod'
        'imagemin'
    ]

    copy_prod: [
        'copy:libs'
        'copy:fonts'
        'copy:common'
        'copy:js'
    ]
