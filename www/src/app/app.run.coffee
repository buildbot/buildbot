angular.module('app').run [
    '$rootScope', '$log', 'config', 'alert', ($rootScope, $log, config, alert) ->
        # fire an event related to the current route
        $rootScope.$on '$routeChangeSuccess', (event, currentRoute, priorRoute) ->
            $rootScope.$broadcast "#{currentRoute.controller}$routeChangeSuccess",
                                  currentRoute, priorRoute
        if config.on_load_warning?
            setTimeout ->
                alert.warning(config.on_load_warning)
                console.log config.on_load_warning
            , 500
    ]

config = @config
@config = undefined  # prevent modules to access config via the global variable
config ?= {plugins: {}, url: "", devmode: true}

# make the config global variable accessible as a DI module
# so that it can be mocked in tests
angular.module('buildbot.common').constant("config", config)
angular.module('bowerconfigs',[]).constant("bowerconfigs", {})
