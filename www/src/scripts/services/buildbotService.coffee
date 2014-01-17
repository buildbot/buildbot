angular.module('app').service 'singulars', ['plurals', (plurals) ->
    ret = {}
    for k, v of plurals
        ret[v] = k
    return ret
]
angular.module('app').factory 'buildbotService',
['$log', 'Restangular', 'mqService', '$rootScope', 'BASEURLAPI',
    'BASEURLSSE', 'plurals', 'singulars', '$q', '$timeout', 'config',
    ($log, Restangular, mqService, $rootScope, BASEURLAPI, BASEURLSSE, plurals,
        singulars, $q, $timeout, config) ->
        jsonrpc2_id = 1
        referenceid = 1
        config.unbind_delay ?= 10 * 60 * 1000 # 10 min by default
        # some is added to base service, and restangularized elements
        addSomeAndMemoize = (elem) ->
            memoize = (f) ->
                return _.memoize f, (a,b,c) ->
                    return [a,b,c].toString()
            # all will be memoized later, so we need to save the unmemoized version
            elem.unmemoized_all = elem.all
            elem.some = memoize (route, queryParams) ->
                new_elem = elem.unmemoized_all(route)
                new_elem.queryParams = queryParams
                return new_elem
            elem.one = memoize(elem.one)
            elem.all = memoize(elem.all)

        responseExtractor =  (response, operation) ->
            if operation == "post"
                return response
            # for now, we only support one resource type per request
            # we'll have to figure out how to support aggregated response at
            # some point because this will be a big improve in latency
            # so we return the first elem that we now the type
            for k, v of response
                if singulars.hasOwnProperty(k)
                    id = singulars[k] + "id"
                    for value in v
                        value["id"] = value[id]
                        value["_raw_data"] = angular.copy(value)
                    if operation == "getList"
                        return v
                    else
                        return v[0]
            throw Error("got unexpected value from data api: #{JSON.stringify(response)},
                         expected one of #{JSON.stringify(singulars)}")

        onElemRestangularized = (elem, isCollection, route, Restangular) ->
            idkey = singulars[elem.route] + "id"

            # list the callers that reference this elem
            references = {}
            events = []
            bound = false

            unbind = ->
                # dont unbind, if some scope is still holding a reference to us
                if _.size(references) != 0
                    return
                for e in events
                    e()
                bound = false
                events = []

            # private backend to elem.bind()
            bind = (opts) ->
                if bound
                    return $q.when(elem.value)
                bound = true
                if (isCollection)
                    onNewOrChange = (value) ->
                        $q.when(elem.value).then (l) ->
                            # de-duplicate, if the element is already there
                            for e in l
                                if e[idkey] == value[idkey]
                                    for k, v of value
                                        e[k] = v
                                    return
                            if not _.isArray(l)
                                debugger
                            value["id"] = value[idkey]
                            value["_raw_data"] = angular.copy(value)
                            # restangularize the object before putting it in
                            # this allows controllers to get more data within onchild()
                            newobj = self.restangularizeElement(elem.parentResource, value, route)
                            # @todo, on new events, need to re-filter through queryParams..
                            l.push(newobj)
                            for k, ref of references
                                ref.onchild(newobj)

                    p = elem.on("*/*", onNewOrChange).then (unsub) ->
                        events.push(unsub)
                        return elem.getList(elem.queryParams).then (res) ->
                            elem.value = res
                            return res

                else
                    onUpdate = (msg) ->
                        _.assign(elem.value, msg)

                    p = elem.get().then (res) ->
                        elem.value = res
                        if opts.ismutable(res)
                            elem.on("*", onUpdate).then (unsub) ->
                                events.push(unsub)
                        return res
                elem.value = p
                return p

            elem.bind = ($scope, opts) ->
                # manage default options
                opts ?= {}
                _.defaults opts,
                    dest_key: if isCollection then route else singulars[route]
                    dest: $scope
                    ismutable: (v) ->
                        if v.complete?
                            return not v.complete
                        return false
                    onchild: ->

                # manage scope that references this elem
                myreferenceid = referenceid += 1
                references[referenceid] =
                    onchild: opts.onchild

                ondestroy = ->
                    delete references[myreferenceid]
                    # we only unbind after a few delay, so that other scope has
                    # a chance to reuse the data or if the user navigate back to the page
                    if _.size(references) == 0
                        $timeout(unbind, config.unbind_delay)
                $scope.$on("$destroy", ondestroy)
                rebind = ->
                    p = bind(opts)
                    p = p.then (res) ->
                        if isCollection
                            for child in res
                                opts.onchild(child)
                        opts.dest[opts.dest_key] = res
                        unsub_lostsync = $rootScope.$on "lost-sync", ->
                            unsub_lostsync()
                            delete references[myreferenceid]
                            unbind()
                            rebind()
                        return res
                    return p
                return rebind()

            elem.on = (event, onEvent) ->
                path = elem.getRestangularUrl().replace(BASEURLAPI,"")
                return mqService.on( path + "/" + event, onEvent)


            elem.control = (method, params) ->
                # do jsonrpc2.0 like POST
                id = jsonrpc2_id++
                req =
                    method: method
                    id: id
                    params: params
                    jsonrpc: "2.0"
                return elem.post("", req)

            addSomeAndMemoize(elem)
            return elem
        configurer = (RestangularConfigurer) ->
            RestangularConfigurer.setBaseUrl(BASEURLAPI)
            RestangularConfigurer.setOnElemRestangularized(onElemRestangularized)
            RestangularConfigurer.setResponseExtractor(responseExtractor)
            mqService.setBaseUrl(BASEURLSSE)

        self = Restangular.withConfig(configurer)
        self.bindHierarchy = ($scope, $stateParams, paths) ->
            r = self
            l = []
            for path in paths
                r = r.one(path, $stateParams[singulars[path]])
                l.push(r.bind($scope))
            return $q.all(l)
        addSomeAndMemoize(self)
        return self

]
