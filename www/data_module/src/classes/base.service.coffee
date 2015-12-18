class Base extends Factory
    constructor: (dataService, socketService, dataUtilsService) ->
        return class BaseInstance
            constructor: (object, @_endpoint, childEndpoints = []) ->
                if not angular.isString(@_endpoint)
                    throw new TypeError("Parameter 'endpoint' must be a string, not #{typeof @endpoint}")

                # add object fields to the instance
                @update(object)

                # generate loadXXX functions
                @constructor.generateFunctions(childEndpoints)

                # get the id of the class type
                classId = dataUtilsService.classId(@_endpoint)
                @_id = @[classId]

                # reset endpoint to base
                if @_id?
                    @_endpoint = dataUtilsService.type(@_endpoint)
                # subscribe for WebSocket events
                @subscribe()

            update: (o) ->
                angular.merge(@, o)

            get: (args...) ->
                dataService.get(@_endpoint, @_id, args...)

            subscribe: ->
                listener = (data) =>
                    key = data.k
                    message = data.m
                    # filter for relevant message
                    streamRegex = ///^#{@_endpoint}\/#{@_id}\/\w+$///g
                    # update when the key matches the instance
                    if streamRegex.test(key) then @update(message)
                @_unsubscribeEventListener = socketService.eventStream.subscribe(listener)
                # _listenerId is required by the stopConsuming logic in dataService
                @_listenerId = listener.id

            unsubscribe: ->
                # unsubscribe childs
                for k, v of this
                    if angular.isArray(v)
                        v.forEach (e) -> e.unsubscribe() if e instanceof BaseInstance
                @_unsubscribeEventListener()

            # generate endpoint functions for the class
            @generateFunctions: (endpoints) ->
                endpoints.forEach (e) =>
                    # capitalize endpoint names
                    E = dataUtilsService.capitalize(e)
                    # adds loadXXX functions to the prototype
                    @::["load#{E}"] = (args...) ->
                        p = @get(e, args...)
                        @[e] = p.getArray()
                        return p
                    # adds getXXX functions to the prototype
                    @::["get#{E}"] = (args...) ->
                        return @get(e, args...)
