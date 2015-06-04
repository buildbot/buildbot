class Base extends Factory
    constructor: (dataService, socketService, dataUtilsService) ->
        return class BaseInstance
            constructor: (object, @endpoint, childEndpoints = []) ->
                if not angular.isString(@endpoint)
                    throw new TypeError("Parameter 'endpoint' must be a string, not #{typeof @endpoint}")

                # add object fields to the instance
                @update(object)

                # generate loadXXX functions
                @constructor.generateFunctions(childEndpoints)

                # get the id of the class type
                classId = dataUtilsService.classId(@endpoint)
                @id = @[classId]

                # subscribe for WebSocket events
                @subscribe()

            update: (o) ->
                angular.merge(@, o)

            get: (args...) ->
                dataService.get(@endpoint, @id, args...)

            subscribe: ->
                listener = (data) =>
                    key = data.k
                    message = data.m
                    # filter for relevant message
                    streamRegex = ///^#{@endpoint}\/#{@id}\/\w+$///g
                    # update when the key matches the instance
                    if streamRegex.test(key) then @update(message)
                @unsubscribeEventListener = socketService.eventStream.subscribe(listener)
                # listenerId is required by the stopConsuming logic in dataService
                @listenerId = listener.id

            unsubscribe: ->
                # unsubscribe childs
                for k, v of this
                    if angular.isArray(v)
                        v.forEach (e) -> e.unsubscribe() if e instanceof BaseInstance
                @unsubscribeEventListener()

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
