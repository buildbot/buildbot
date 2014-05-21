### ###############################################################################################
#
#   Generates main.js
#   Angular is actually very nice with its dependancy injection system
#   Basically, we just need angular is loaded first, app second and run last
#
### ###############################################################################################
module.exports =

    options:
        order: [
            # order is a list of regular expression matching
            # modules, requiregen will generate the correct shim
            # to load modules in this order
            # if a module has been loaded in previous layers, it wont be loaded again
            # so that you can use global regular expression in the end
            '{,**/}libs/jquery'
            '{,**/}libs/angular'            # angular needs jquery before or will use internal jqlite
            '{,**/}libs/*'                  # remaining libs before app
            '{,**/}test/libs/*'             # test libs in dev mode
            '{,**/}test/**'                 # test mocks in dev mode
            '{,**/}app.module'              # app needs libs
            '{,**/}*.module'                # other module definitions
            '{,**/}config'                  # bower configs
            '{,**/}*{.constant,.filter,.service,.controller,.directive,.route,.config,.templates}'
                                            # other AngularJS components
            '{,**/}app.run'                 # run has to be in the end, because it is triggering
                                            # AngularJS's own DI
        ]
        define: true

    generate:
        cwd: '<%= dir.temp %>/scripts'
        src: ['**/*.js', '!libs/require.js']
        dest: '<%= dir.temp %>/scripts/main.js'