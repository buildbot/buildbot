angular.module('app').factory 'EventSource', ->
    # turn HTML5's EventSource into a angular module for mockability
    return (url)->
        return new EventSource(url)
BASEURLAPI = 'api/v2/'
BASEURLSSE = 'sse/'
angular.module('app').factory 'buildbotService',
['$log', 'Restangular', 'EventSource',
    ($log, Restangular, EventSource) ->
        configurer = (RestangularConfigurer) ->
            onElemRestangularized = (elem, isCollection, route, Restangular) ->
                # add the bind() method to each restangular object
                # bind method will create one way binding (readonly)
                # via event source
                elem.bind = ($scope, scope_key) ->
                    if not scope_key?
                        scope_key = elem.route
                    if (isCollection)
                        onEvent = (e) ->
                            $scope[scope_key].push(e.msg)
                            $scope.$apply()
                        p = elem.getList()
                        p.then((v) ->
                            $scope[scope_key] = v
                            elem.on("new", onEvent)
                            return v
                        )
                    else
                        onEvent = (e) ->
                            for k, v of e.msg
                                $scope[scope_key][k] = v
                            $scope.$apply()
                        p = this.get()
                        p.then((v) ->
                            $scope[scope_key] = v
                            elem.on("update", onEvent)
                            return v
                        )
                    $scope.$on("$destroy", -> elem.source?.close())
                    $scope[scope_key] = p
                    return p

                elem.unbind = () ->
                    this.source?.close()

                elem.on = (event, onEvent) ->
                    if not elem.source?
                        route = elem.getRestangularUrl()
                        route = route.replace(BASEURLAPI, BASEURLSSE)
                        source = new EventSource(route)
                        elem.source = source
                    elem.source.addEventListener(event, onEvent)
                return elem
            RestangularConfigurer.setBaseUrl(BASEURLAPI)
            RestangularConfigurer.setOnElemRestangularized(onElemRestangularized)

        return Restangular.withConfig(configurer)

]
