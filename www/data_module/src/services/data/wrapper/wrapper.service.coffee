class Wrapper extends Factory
    constructor: ($log, dataService, dataUtilsService, tabexService, SPECIFICATION) ->
        return class WrapperInstance
            constructor: (object, endpoint) ->
                if not angular.isString(endpoint)
                    throw new TypeError("Parameter 'endpoint' must be a string, not #{typeof endpoint}")
                @getEndpoint = -> endpoint

                # add object fields to the instance
                @update(object)

                # generate loadXXX functions
                endpoints = Object.keys(SPECIFICATION)
                @constructor.generateFunctions(endpoints)

            update: (o) ->
                angular.merge(@, o)

            get: (args...) ->
                [root, id, path...] = @getEndpoint().split('/')
                [options..., last] = args
                if angular.isObject(last)
                    pathString = path.concat('*', options).join('/')
                else
                    pathString = path.concat('*', args).join('/')
                if path.length == 0
                    return dataService.get(@getEndpoint(), @getId(), args...)

                specification = SPECIFICATION[root]
                match = specification.paths.filter (p) ->
                    replaced = p
                        .replace ///\w+\:\w+///g, '\\*'
                    ///^#{replaced}$///.test(pathString)
                .pop()
                if not match?
                    parameter = @getId()

                # second last element
                for e in match.split('/') by -1
                    if e.indexOf(':') > -1
                        [fieldType, fieldName] = e.split(':')
                        parameter = @[fieldName]

                dataService.get(@getEndpoint(), parameter, args...)

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

            getId: ->
                @[@classId()]

            getIdentifier: ->
                @[@classIdentifier()]

            classId: ->
                SPECIFICATION[dataUtilsService.type(@getEndpoint())].id

            classIdentifier: ->
                SPECIFICATION[dataUtilsService.type(@getEndpoint())].identifier

            unsubscribe: ->
                e?.unsubscribe?() for _, e of this
