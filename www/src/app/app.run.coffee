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
