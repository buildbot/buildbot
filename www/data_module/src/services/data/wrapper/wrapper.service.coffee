class Wrapper extends Factory
    constructor: ($log, dataService, dataUtilsService, tabexService, SPECIFICATION) ->
        return class WrapperInstance
            constructor: (object, endpoint, @_subscribe) ->
                if not angular.isString(endpoint)
                    throw new TypeError("Parameter 'endpoint' must be a string, not #{typeof endpoint}")
                @_endpoint = endpoint

                # add object fields to the instance
                @update(object)

                # generate getXXX, and loadXXX functions
                endpoints = Object.keys(SPECIFICATION)
                @constructor.generateFunctions(endpoints)

            update: (o) ->
                angular.merge(@, o)

            get: (args...) ->
                [root, id, path...] = @_endpoint.split('/')
                [options..., last] = args
                if angular.isObject(last)
                    pathString = path.concat('*', options).join('/')
                    if @_subscribe? then args[args.length - 1].subscribe ?= @_subscribe
                else
                    pathString = path.concat('*', args).join('/')
                    if @_subscribe? then args.push(subscribe: @_subscribe)
                if path.length == 0
                    return dataService.get(@_endpoint, @getId(), args...)

                specification = SPECIFICATION[root]
                match = specification.paths.filter (p) ->
                    replaced = p
                        .replace ///\w+\:\w+///g, '(\\*|\\w+|\\d+)'
                    ///^#{replaced}$///.test(pathString)
                .pop()
                if not match?
                    parameter = @getId()
                else
                    # second last element
                    for e in match.split('/')[...-1] by -1
                        if e.indexOf(':') > -1
                            [fieldType, fieldName] = e.split(':')
                            parameter = @[fieldName]
                            break

                dataService.get(@_endpoint, parameter, args...)

            control: (method, params) ->
                dataService.control("#{@_endpoint}/#{@getIdentifier() or @getId()}", method, params)

            # generate endpoint functions for the class
            @generateFunctions: (endpoints) ->
                endpoints.forEach (e) =>
                    if e == e.toUpperCase() then return
                    # capitalize endpoint names
                    E = dataUtilsService.capitalize(e)
                    # adds getXXX functions to the prototype
                    @::["get#{E}"] ?= (args...) ->
                        return @get(e, args...)
                    # adds loadXXX functions to the prototype
                    @::["load#{E}"] ?= (args...) ->
                        p = @get(e, args...)
                        @[e] = p.getArray()
                        return p

            getId: ->
                @[@classId()]

            getIdentifier: ->
                @[@classIdentifier()]

            classId: ->
                SPECIFICATION[dataUtilsService.type(@_endpoint)].id

            classIdentifier: ->
                SPECIFICATION[dataUtilsService.type(@_endpoint)].identifier

            unsubscribe: ->
                e?.unsubscribe?() for _, e of this
