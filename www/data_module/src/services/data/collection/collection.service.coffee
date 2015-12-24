class Collection extends Factory
    constructor: ($q, $injector, $log, dataUtilsService, socketService) ->
        return class CollectionInstance extends Array
            constructor: (@restPath, @query = {}, @accessor) ->
                @socketPath = dataUtilsService.socketPath(@restPath)
                @type = dataUtilsService.type(@restPath)
                @id = dataUtilsService.classId(@restPath)
                @endpoint = dataUtilsService.endpointPath(@restPath)
                @socketPathRE = ///^#{@restPath}\/(\w+|\d+)\/.*$///g

                # default event handlers
                @onChange = angular.nop
                @onNew = angular.nop
                @onChange = angular.nop

                try
                    # try to get the wrapper class
                    className = dataUtilsService.className(@restPath)
                    # the classes have the dataService as a dependency
                    # $injector.get doesn't throw circular dependency exception
                    @WrapperClass = $injector.get(className)
                catch e
                    # use the Base class otherwise
                    console.log "unknown wrapper for", className
                    @WrapperClass = $injector.get('Base')
                socketService.eventStream.subscribe(@listener)
                @accessor?.registerCollection(this)

            listener: (data) =>
                key = data.k
                message = data.m
                # Test if the message is for me
                if @socketPathRE.test(key)
                    @put(message)
                    @recomputeQuery()

            subscribe: ->
                return socketService.subscribe(@socketPath, this)

            close: ->
                return socketService.unsubscribe(@socketPath, this)

            from: (data) ->
                # put items one by one
                @put(i) for i in data
                @recomputeQuery()

            add: (element) ->
                instance = new @WrapperClass(element, @endpoint)
                instance.setAccessor(@accessor)
                @push(instance)

            put: (element) ->
                for old in this
                    if old[@id] == element[@id]
                        old.update(element)
                        return true
                # if not found, add it.
                @add(element)
                return false
            clear: ->
                @pop() while @length > 0

            delete: (element) ->
                index = @indexOf(element)
                if index > -1 then @splice(index, 1)

            recomputeQuery: ->
