class Data extends Provider
    constructor: ->
    # TODO caching
    cache: false

    ### @ngInject ###
    $get: ($log, $injector, $q, restService, socketService, dataUtilsService, Collection, ENDPOINTS) ->
        return new class DataService
            self = null
            constructor: ->
                self = this
                # setup socket listeners
                #socketService.eventStream.onUnsubscribe = @unsubscribeListener
                socketService.onclose = @socketCloseListener
                # generate loadXXX functions for root endpoints
                @constructor.generateEndpoints()

            # the arguments are in this order: endpoint, id, child, id of child, query
            get: (args...) ->

                # get the query parameters
                [args, query] = dataUtilsService.splitOptions(args)
                subscribe = accessor = undefined

                # subscribe for changes if 'subscribe' is true
                subscribe = query.subscribe == true
                accessor = query.accessor
                if subscribe and not accessor
                    $log.warn "subscribe call should be done after DataService.open()"
                    $log.warn "for maintaining trace of observers"
                    subscribe = false

                # 'subscribe' is not part of the query
                delete query.subscribe
                delete query.accessor

                restPath = dataUtilsService.restPath(args)
                # up to date array, this will be returned
                collection = new Collection(restPath, query, accessor)

                if subscribe
                    subscribePromise = collection.subscribe()
                else
                    subscribePromise = $q.resolve()

                subscribePromise.then ->
                    # get the data from the rest api
                    restService.get(restPath, query).then (response) ->

                        type = dataUtilsService.type(restPath)
                        datalist = response[type]
                        # the response should always be an array
                        if not angular.isArray(datalist)
                            e = "#{datalist} is not an array"
                            $log.error(e)
                            return

                        # fill up the collection with initial data
                        collection.initial(datalist)

                return collection


            control: (ep, id, method, params = {}) ->
                restPath = dataUtilsService.restPath([ep, id])
                restService.post restPath,
                    id: @getNextId()
                    jsonrpc: '2.0'
                    method: method
                    params: params

            # returns next id for jsonrpc2 control messages
            getNextId: ->
                @jsonrpc ?= 1
                @jsonrpc++

            # generate functions for root endpoints
            @generateEndpoints: ->
                ENDPOINTS.forEach (e) =>
                    # capitalize endpoint names
                    E = dataUtilsService.capitalize(e)
                    this::["get#{E}"] = (args...) ->
                        self.get(e, args...)

            # opens a new accessor
            open: ->
                return new class DataAccessor
                    collectionRefs = []
                    constructor: ->
                        @constructor.generateEndpoints()

                    registerCollection: (c) ->
                        collectionRefs.push(c)

                    close: ->
                        collectionRefs.forEach (c) -> c.close()

                    # Closes the group when the scope is destroyed
                    closeOnDestroy: (scope) ->
                        if not angular.isFunction(scope.$on)
                            throw new TypeError("Parameter 'scope' doesn't have an $on function")
                        scope.$on '$destroy', => @close()
                        return this

                    # Generate functions for root endpoints
                    @generateEndpoints: ->
                        ENDPOINTS.forEach (e) =>
                            # capitalize endpoint names
                            E = dataUtilsService.capitalize(e)
                            this::["get#{E}"] = (args...) ->
                                [args, query] = dataUtilsService.splitOptions(args)
                                query.subscribe ?= true
                                query.accessor = this
                                return self.get(e, args..., query)

        ############## utils for testing
        # register return values for the mocked get function
            mocks: {}
            spied: false
            when: (url, query, returnValue) ->
                if not returnValue?
                    [query, returnValue] = [{}, query]
                if jasmine? and not @spied
                    spyOn(this, 'get').and.callFake(@_mockGet)
                    @spied = true

                @mocks[url] ?= {}
                @mocks[url][query] = returnValue

            expect: (url, query, returnValue) ->
                if not returnValue?
                    [query, returnValue] = [{}, query]
                @_expects ?= []
                @_expects.push([url, query])
                @when(url, query, returnValue)

            verifyNoOutstandingExpectation:  ->
                if @_expects? and @_expects.length
                    fail("expecting #{@_expects.length} more data requests " +
                        "(#{angular.toJson(@_expects)})")

            # register return values with the .when function
            # when testing get will return the given values
            _mockGet: (args...) ->
                [url, query] = @processArguments(args)
                queryWithoutSubscribe = {}
                for k, v of query
                    if k != "subscribe" and k != "accessor"
                        queryWithoutSubscribe[k] = v
                if @_expects
                    [exp_url, exp_query] = @_expects.shift()
                    expect(exp_url).toEqual(url)
                    expect(exp_query).toEqual(queryWithoutSubscribe)
                returnValue = @mocks[url]?[query] or @mocks[url]?[queryWithoutSubscribe]
                if not returnValue? then throw new Error("No return value for: #{url} " +
                    "(#{angular.toJson(queryWithoutSubscribe)})")
                collection = @createCollection(url, queryWithoutSubscribe, returnValue)
                return collection

            processArguments: (args) ->
                [args, query] = dataUtilsService.splitOptions(args)
                restPath = dataUtilsService.restPath(args)
                return [restPath, query or {}]


            # for easier testing
            createCollection: (url, query, response) ->
                restPath = url
                type = dataUtilsService.type(restPath)
                collection = new Collection(restPath, query)

                # populate the response with default ids
                # for convenience
                id = collection.id
                idCounter = 1
                response.forEach (d) ->
                    if not d.hasOwnProperty(id)
                        d[id] = idCounter++

                collection.initial(response)
                return collection
