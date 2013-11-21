angular.module('app').factory 'EventSource', ->
    # turn HTML5's EventSource into a angular module for mockability
    return (url)->
        return new EventSource(url)
BASEURLAPI = 'api/v2/'
BASEURLSSE = 'sse/'
jsonrpc2_id = 1
angular.module('app').factory 'buildbotService',
['$log', 'Restangular', 'EventSource', '$rootScope'
    ($log, Restangular, EventSource, $rootScope ) ->
        configurer = (RestangularConfigurer) ->
            responseExtractor =  (response) ->
                # for now, we only support one resource type per request
                # we'll have to figure out how to support aggregated response at
                # some point because this will be a big improve in latency
                # so we return the first elem that is not "meta"
                for k, v of response
                    if k != "meta"
                        for b in v
                            # FIXME: fix the data api to always provide a 'id' key
                            # as jsonapi (and restangular) is requiring
                            b.id ?= b.builderid
                        return v
                response
            onElemRestangularized = (elem, isCollection, route, Restangular) ->
                # add the bind() method to each restangular object
                # bind method will create one way binding (readonly)
                # via event source
                elem.bind = ($scope, scope_key) ->
                    if not scope_key?
                        scope_key = elem.route
                    if (isCollection)
                        onEvent = (e) ->
                            console.log "new in service", e
                            e.msg = JSON.parse(e.data)
                            $scope[scope_key].push(e.msg)
                            elem.one(e.msg.number).bind($scope[scope_key], $scope[scope_key].length - 1)
                            $rootScope.$apply()
                        p = elem.getList()
                        p = p.then (res) ->
                            $scope[scope_key] = res
                            elem.on("new", onEvent)
                            return res
                    else
                        onEvent = (e) ->
                            console.log e
                            e.msg = JSON.parse(e.data)
                            for k, v of e.msg
                                $scope[scope_key][k] = v
                            $rootScope.$apply()
                        p = this.getList() # all is list with jsonAPI
                        p = p.then (res) ->
                            $scope[scope_key] = res[0]
                            elem.on("update", onEvent)
                            return res
                    $scope.$on?("$destroy", -> elem.source?.close())
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

                elem.control = (method, params) ->
                    # do jsonrpc2.0 like POST
                    id = jsonrpc2_id++
                    req =
                        method: method
                        id: id
                        params: params
                        jsonrpc: "2.0"
                    return elem.post("", req)

                return elem
            RestangularConfigurer.setBaseUrl(BASEURLAPI)
            RestangularConfigurer.setOnElemRestangularized(onElemRestangularized)
            RestangularConfigurer.setResponseExtractor(responseExtractor)
        return Restangular.withConfig(configurer)

]
