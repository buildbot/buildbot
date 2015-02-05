class RouteChangeListener extends Run
    constructor: ($rootScope, $log, config, glNotificationService, $wamp) ->
        # fire an event related to the current route
        $rootScope.$on '$routeChangeSuccess', (event, currentRoute, priorRoute) ->
            $rootScope.$broadcast "#{currentRoute.controller}$routeChangeSuccess",
                                  currentRoute, priorRoute
        if config.on_load_warning?
            setTimeout ->
                glNotificationService.notify(msg:config.on_load_warning)
            , 500
        if not window.__karma__?
            $wamp.open()
