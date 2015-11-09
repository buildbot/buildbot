class Collection extends Factory
    constructor: ($q, $injector, $log, dataUtilsService) ->
        return class CollectionInstance extends Array
            constructor: (restPath, query = {}) ->
                @getRestPath = -> restPath
                @getQuery = -> query
                @getSocketPath = -> dataUtilsService.socketPath(restPath)
                @getType = -> dataUtilsService.type(restPath)
                id = dataUtilsService.classId(restPath)
                @getId = -> id
                @getEndpoint = -> dataUtilsService.endpointPath(restPath)
                streamRegex = ///^#{restPath}\/(\w+|\d+)\/.*$///g
                @getSocketPathRE = -> streamRegex
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
                @getWrapper = -> WrapperClass

                @subscribers = []

            subscribe: (subscriber) ->
                if @subscribers.indexOf(subscriber) < 0
                    @subscribers.push(subscriber)

            unsubscribe: (subscriber) ->
                i = @subscribers.indexOf(subscriber)
                if i >= 0
                    @subscribers.splice(i, 1)

            listener: (data) =>
                key = data.k
                message = data.m
                # Test if the message is for me
                if @getSocketPathRE().test(key)
                    @put(message)
                    @recomputeQuery()

            from: (data) ->
                # put items one by one
                @put(i) for i in data
                @recomputeQuery()

            add: (element) ->
                Wrapper = @getWrapper()
                instance = new Wrapper(element, @getEndpoint(), @getQuery().subscribe)
                @push(instance)

            put: (element) ->
                id = @getId()
                for old in this
                    if old[id] == element[id]
                        old.update(element)
                        return
                # if not found, add it.
                @add(element)

            clear: ->
                @pop() while @length > 0

            delete: (element) ->
                index = @indexOf(element)
                if index > -1 then @splice(index, 1)

            recomputeQuery: ->
