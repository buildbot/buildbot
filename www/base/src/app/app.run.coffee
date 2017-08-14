class RouteChangeListener extends Run
    constructor: ($rootScope, $log, config, glNotificationService) ->
        # fire an event related to the current route
        $rootScope.$on '$routeChangeSuccess', (event, currentRoute, priorRoute) ->
            $rootScope.$broadcast "#{currentRoute.controller}$routeChangeSuccess",
                                  currentRoute, priorRoute
        if config.on_load_warning?
            setTimeout ->
                glNotificationService.notify(msg:config.on_load_warning)
            , 500

# FIXME hack to reload the window if the websocket is disconnected
# We should fix properly in dataModule using :bug:`3462`, but after initial nine release

# fix in dataModule is much harder, as when reconnection is detected, we should
# reload all watched collections, take care of sending the proper events, etc
class ReconnectingListener extends Run
    constructor: ($rootScope, $log, socketService, $interval, $http, $window, $timeout) ->

        reconnecting = false
        hasBeenConnected = false
        # first poll for an initial connected socket
        # we cannot really use events, as we are not doing this inside dataModule
        interval = $interval ->
            if socketService.socket?
                if socketService.socket.readyState == 1 and not hasBeenConnected
                    $interval.cancel(interval)
                    interval = null
                    hasBeenConnected = true
                    socketService.socket.onclose = (evt) ->
                        # ignore if we are navigating away from buildbot
                        # see https://github.com/buildbot/buildbot/issues/3306
                        if evt.code <= 1001  # CLOSE_GOING_AWAY or CLOSE_NORMAL
                            return
                        reconnecting = true
                        $rootScope.$apply ->
                            # send event to connectionstatus directive
                            $rootScope.$broadcast("mq.lost_connection")
                        reloadWhenReady()
        , 1000

        # following code do the polling of reconnection, and eventually
        # reload the document, when we managed to get the index page
        # we avoid to do that polling if the tab is hidden
        $window.document.addEventListener "visibilitychange", ->
            if not $window.document.hidden and reconnecting
                reloadWhenReady()

        reloadWhenReady = ->
            # if the window/tab is hidden, we stop the polling
            # if browser does not support visibility api, this will just always poll
            if $window.document.hidden
                return
            $http.get($window.document.location.href).then ->
                # send event to connectionstatus directive
                $rootScope.$broadcast("mq.restored_connection")

                # wait one second before actually reload to let user to see message
                $timeout (-> $window.document.location.reload()), 1000
            , ->
                # error callback: if we cannot connect, we will retry in 3 seconds
                $timeout reloadWhenReady, 3000
