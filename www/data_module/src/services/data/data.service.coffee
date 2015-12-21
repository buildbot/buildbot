class Data extends Provider
    constructor: ->
    # TODO caching
    cache: false

    ### @ngInject ###
    $get: ($log, $injector, $q, restService, socketService, dataUtilsService, ENDPOINTS) ->
        return new class DataService
            self = null
            constructor: ->
                self = @
                # setup socket listeners
                #socketService.eventStream.onUnsubscribe = @unsubscribeListener
                socketService.onclose = @socketCloseListener
                # generate loadXXX functions for root endpoints
                @constructor.generateEndpoints()

            # the arguments are in this order: endpoint, id, child, id of child, query
            get: (args...) ->
                # keep defined arguments only
                args = args.filter (e) -> e?

                # get the query parameters
                [..., last] = args
                # subscribe for changes if 'subscribe' is true or undefined
                subscribe = last.subscribe or not last.subscribe?
                if angular.isObject(last)
                    query = args.pop()
                    # 'subscribe' is not part of the query
                    delete query.subscribe

                # up to date array, this will be returned
                updating = []

                promise = $q (resolve, reject) =>

                    if subscribe
                        # TODO needs testing
                        # store all messages before the classes subscribe for changes
                        # resend once those are ready
                        messages = []
                        unsubscribe = socketService.eventStream.subscribe (data) ->
                            messages.push(data)

                        # start consuming WebSocket messages
                        socketPath = dataUtilsService.socketPath(args)
                        socketPromise = @startConsuming(socketPath)
                    else socketPromise = $q.resolve()

                    socketPromise.then =>
                        # get the data from the rest api
                        restPath = dataUtilsService.restPath(args)
                        restPromise = restService.get(restPath, query)

                        restPromise.then (response) =>

                            type = dataUtilsService.type(restPath)
                            response = response[type]
                            try
                                # try to get the wrapper class
                                className = dataUtilsService.className(restPath)
                                # the classes have the dataService as a dependency
                                # $injector.get doesn't throw circular dependency exception
                                WrapperClass = $injector.get(className)
                            catch e
                                # use the Base class otherwise
                                console.log "unknown wrapper for", className
                                WrapperClass = $injector.get('Base')
                            # the response should always be an array
                            if angular.isArray(response)
                                # strip the id or name from the path if it's there
                                endpoint = dataUtilsService.endpointPath(args)
                                # wrap the elements in classes
                                response = response.map (i) -> new WrapperClass(i, endpoint)
                                # map of path: [listener id]
                                @listeners ?= {}
                                # add listener ids to the socket path
                                @listeners[socketPath] ?= []
                                response.forEach (r) =>
                                    @listeners[socketPath].push(r._listenerId)
                                # handle /new messages
                                socketService.eventStream.subscribe (data) =>
                                    key = data.k
                                    message = data.m
                                    # filter for relevant message
                                    streamRegex = ///^#{endpoint}\/(\w+|\d+)\/new$///g
                                    # add new instance to the updating array
                                    if streamRegex.test(key)
                                        newInstance = new WrapperClass(message, endpoint)
                                        updating.push(newInstance)
                                        @listeners[socketPath].push(newInstance._listenerId)
                                # TODO needs testing
                                # resend messages
                                if subscribe
                                    messages.forEach (m) -> socketService.eventStream.push(m)
                                    unsubscribe()
                                # fill up the updating array
                                angular.copy(response, updating)
                                # the updating array is ready to be used
                                resolve(updating)
                            else
                                e = "#{response} is not an array"
                                $log.error(e)
                                reject(e)
                        , (e) => reject(e)
                    , (e) => reject(e)

                promise.getArray = -> updating

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

            control: (method, params) ->
                restService.post
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
                    @::["get#{E}"] = (args...) =>
                        self.get(e, args...)

            # opens a new accessor
            open: ->
                return new class DataAccessor
                    rootClasses = []
                    constructor: ->
                        @rootClasses = rootClasses
                        @constructor.generateEndpoints()

                    # calls unsubscribe on each root classes
                    close: ->
                        @rootClasses.forEach (c) -> c.unsubscribe()

                    # closes the group when the scope is destroyed
                    closeOnDestroy: (scope) ->
                        if not angular.isFunction(scope.$on)
                            throw new TypeError("Parameter 'scope' doesn't have an $on function")
                        scope.$on '$destroy', => @close()

                    # generate functions for root endpoints
                    @generateEndpoints: ->
                        ENDPOINTS.forEach (e) =>
                            # capitalize endpoint names
                            E = dataUtilsService.capitalize(e)
                            @::["get#{E}"] = (args...) =>
                                p = self["get#{E}"](args...)
                                # when the promise is resolved add the root level classes
                                # to an array (on close we can call unsubscribe on those)
                                p.then (classes) ->
                                    classes.forEach (c) -> rootClasses.push(c)
                                return p

        ############## utils for testing
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
                collection = @createCollection(url, query, returnValue)
                p = $q.resolve(collection)
                p.getArray = -> collection
                return p

            processArguments: (args) ->
                # keep defined arguments only
                args.filter (e) -> e?
                # get the query parameters
                [..., last] = args
                if angular.isObject(last)
                    query = args.pop()
                restPath = dataUtilsService.restPath(args)
                return [restPath, query or {}]


            # for easier testing
            createCollection: (url, query, response) ->
                restPath = url
                type = dataUtilsService.type(restPath)
                try
                    # try to get the wrapper class
                    className = dataUtilsService.className(restPath)
                    # the classes have the dataService as a dependency
                    # $injector.get doesn't throw circular dependency exception
                    WrapperClass = $injector.get(className)
                catch e
                    # use the Base class otherwise
                    console.log "unknown wrapper for", className
                    WrapperClass = $injector.get('Base')
                # strip the id or name from the path if it's there
                endpoint = dataUtilsService.endpointPath([restPath])
                # wrap the elements in classes
                response = response.map (i) -> new WrapperClass(i, endpoint)
