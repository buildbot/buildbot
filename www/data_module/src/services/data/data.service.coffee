class Data extends Provider
    cache: true
    config = null
    constructor: ->
        config = cache: @cache

    ### @ngInject ###
    $get: ($log, $injector, $q, $window, Collection, restService, dataUtilsService, tabexService, indexedDBService, SPECIFICATION) ->
        return new class DataService
            self = null
            constructor: ->
                self = @
                angular.extend(@, config)
                # generate loadXXX functions for root endpoints
                endpoints = Object.keys(SPECIFICATION).filter (e) -> SPECIFICATION[e].id?
                @constructor.generateEndpoints(endpoints)

            clearCache: ->
                indexedDBService.clear().then ->
                    if $injector.has('$state')
                        $injector.get('$state').reload()
                    else if $injector.has('$route')
                        $injector.get('$route').reload()
                    else
                        $window.location.reload()

            # the arguments are in this order: endpoint, id, child, id of child, query
            get: (args...) ->

                [restPath, query] = @processArguments(args)
                query.subscribe ?= false

                # up to date collection, this will be returned
                collection = @createCollection(restPath, query)
                collection.subscribe()

            # register return values for the mocked get function
            mocks: {}
            spied: false
            when: (args...) ->
                [url, query, returnValue] = args
                if not returnValue?
                    [query, returnValue] = [{}, query]
                if jasmine? and not @spied
                    spyOn(@, 'get').and.callFake(@_mockGet)
                    @spied = true

                @mocks[url] ?= {}
                @mocks[url][query] = returnValue

            # register return values with the .when function
            # when testing get will return the given values
            _mockGet: (args...) ->
                [url, query] = @processArguments(args)
                queryWithoutSubscribe = angular.copy(query)
                delete queryWithoutSubscribe.subscribe
                returnValue = @mocks[url]?[query] or @mocks[url]?[queryWithoutSubscribe]
                if not returnValue? then throw new Error("No return value for: #{url} (#{angular.toJson(query)})")
                collection = @createCollection(url, query)
                collection.from(returnValue)
                p = $q.resolve(collection)
                p.getArray = -> collection
                return p

            # for easier testing
            createCollection: (args...) ->
                new Collection(args...)

            processArguments: (args) ->
                # keep defined arguments only
                args.filter (e) -> e?
                # get the query parameters
                [..., last] = args
                if angular.isObject(last)
                    query = args.pop()
                restPath = dataUtilsService.restPath(args)
                return [restPath, query or {}]

            control: (url, method, params = {}) ->
                @jsonrpc ?= 1
                restService.post url,
                    id: @jsonrpc++
                    jsonrpc: '2.0'
                    method: method
                    params: params

            # generate functions for root endpoints
            @generateEndpoints: (endpoints) ->
                endpoints.forEach (e) =>
                    # capitalize endpoint names
                    E = dataUtilsService.capitalize(e)
                    @::["get#{E}"] = (args...) =>
                        self.get(e, args...)

            # opens a new accessor
            open: (scope) ->
                return new class DataAccessor
                    collections = []
                    constructor: ->
                        @collections = collections
                        # generate getXXX functions for root endpoints
                        endpoints = Object.keys(SPECIFICATION).filter (e) -> SPECIFICATION[e].id?
                        @constructor.generateEndpoints(endpoints)

                        if scope? then @closeOnDestroy(scope)

                    # calls unsubscribe on each root classes
                    close: ->
                        collections.forEach (c) -> c.unsubscribe?()

                    # closes the group when the scope is destroyed
                    closeOnDestroy: (scope) ->
                        if not angular.isFunction(scope.$on)
                            throw new Error("Parameter 'scope' doesn't have an $on function")
                        scope.$on '$destroy', => @close()

                    # generate functions for root endpoints
                    @generateEndpoints: (endpoints) ->
                        endpoints.forEach (e) =>
                            E = dataUtilsService.capitalize(e)
                            @::["get#{E}"] = (args...) =>
                                last = args[args.length - 1]
                                if angular.isObject(last)
                                    last.subscribe ?= true
                                else args.push(subscribe: true)
                                p = self["get#{E}"](args...)
                                collections.push(p.getArray())
                                return p
