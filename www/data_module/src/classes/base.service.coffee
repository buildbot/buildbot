class Base extends Factory
    constructor: (dataService, socketService, dataUtilsService) ->
        return class BaseInstance
            constructor: (object, @_endpoint, childEndpoints = []) ->
                if not angular.isString(@_endpoint)
                    throw new TypeError("Parameter 'endpoint' must be a string, not #{typeof @endpoint}")

                @$accessor = null
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

            setAccessor: (a) ->
                @$accessor = a

            update: (o) ->
                angular.extend(this, o)

            get: (args...) ->
                dataService.get(@_endpoint, @_id, args...)

            control: (method, params) ->
                dataService.control(@_endpoint, @_id, method, params)

            # generate endpoint functions for the class
            @generateFunctions: (endpoints) ->
                endpoints.forEach (e) =>
                    # capitalize endpoint names
                    E = dataUtilsService.capitalize(e)
                    # adds loadXXX functions to the prototype
                    this::["load#{E}"] = (args...) ->
                        return @[e] = @get(e, args...)

                    # adds getXXX functions to the prototype
                    this::["get#{E}"] = (args...) ->
                        [args, query] = dataUtilsService.splitOptions(args)
                        if @$accessor
                            query.subscribe ?= true
                            query.accessor = @$accessor
                        return @.get(e, args..., query)
