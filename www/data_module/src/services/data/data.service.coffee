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

                # subscribe for changes if 'subscribe' is true or undefined
                subscribe = query.subscribe or not query.subscribe?
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

                promise = $q (resolve, reject) ->

                    subscribePromise.then ->
                        # get the data from the rest api
                        restService.get(restPath, query).then (response) ->

                            type = dataUtilsService.type(restPath)
                            response = response[type]
                            # the response should always be an array
                            if not angular.isArray(response)
                                e = "#{response} is not an array"
                                $log.error(e)
                                reject(e)
                                return

                            # fill up the collection with data
                            collection.from(response)
                            # the collection is ready to be used
                            resolve(collection)

                        , (e) -> reject(e)
                    , (e) -> reject(e)

                promise.getArray = -> collection

                return promise

            startConsuming: (path) ->
                socketService.send({
                    cmd: 'startConsuming'
                    path: path
                })

            stopConsuming: (path) ->
                socketService.send({
                    cmd: 'stopConsuming'
                    path: path
                })

            # make the stopConsuming calls when there is no listener for a specific endpoint
            unsubscribeListener: (removed) =>
                for path, ids of @listeners
                    i = ids.indexOf(removed.id)
                    if i > -1
                        ids.splice(i, 1)
                        if ids.length is 0 then @stopConsuming(path)

            # resend the start consuming messages for active paths
            socketCloseListener: =>
                if not @listeners? then return
                for path, ids of @listeners
                    if ids.length > 0 then @startConsuming(path)
                return null

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

                    # Generate functions for root endpoints
                    @generateEndpoints: ->
                        ENDPOINTS.forEach (e) =>
                            # capitalize endpoint names
                            E = dataUtilsService.capitalize(e)
                            this::["get#{E}"] = (args...) ->
                                [args, query] = dataUtilsService.splitOptions(args)
                                query.accessor = this
                                return self.get(e, args..., query)

        ############## utils for testing
        # register return values for the mocked get function
            mocks: {}
            spied: false
            when: (args...) ->
                [url, query, returnValue] = args
                if not returnValue?
                    [query, returnValue] = [{}, query]
                if jasmine? and not @spied
                    spyOn(this, 'get').and.callFake(@_mockGet)
                    @spied = true

                @mocks[url] ?= {}
                @mocks[url][query] = returnValue

            # register return values with the .when function
            # when testing get will return the given values
            _mockGet: (args...) ->
                [url, query] = @processArguments(args)
                queryWithoutSubscribe = angular.copy(query)
                delete queryWithoutSubscribe.subscribe
                delete queryWithoutSubscribe.accessor
                returnValue = @mocks[url]?[query] or @mocks[url]?[queryWithoutSubscribe]
                if not returnValue? then throw new Error("No return value for: #{url} (#{angular.toJson(queryWithoutSubscribe)})")
                collection = @createCollection(url, queryWithoutSubscribe, returnValue)
                p = $q.resolve(collection)
                p.getArray = -> collection
                return p

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

                collection.from(response)
                return collection
