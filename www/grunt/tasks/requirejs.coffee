### ###############################################################################################
#
#   Optimize RequireJS projects using r.js
#
### ###############################################################################################
module.exports =

    optimize:
        options:
            baseUrl: '.temp/scripts/'
            mainConfigFile: '.temp/scripts/main.js'
            name: 'main'
            logLevel: 0
            findNestedDependencies: true
            skipModuleInsertion: true
            out:  '.temp/scripts/main.js'
            optimize: 'uglify2'
            uglify:
                # Let uglifier replace variables to further reduce file size.
                mangle: true
            # Exclude main from the final output to avoid the dependency on
            # RequireJS at runtime.
            onBuildWrite: (moduleName, path, contents) ->
                modulesToExclude = ['main']
                shouldExcludeModule = moduleName in modulesToExclude

                if shouldExcludeModule then '' else contents