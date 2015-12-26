class Collection extends Factory
    constructor: ($q, $injector, $log, dataUtilsService, socketService, DataQuery) ->
        return class CollectionInstance extends Array
            constructor: (@restPath, @query = {}, @accessor) ->
                @socketPath = dataUtilsService.socketPath(@restPath)
                @type = dataUtilsService.type(@restPath)
                @id = dataUtilsService.classId(@restPath)
                console.log @id
                @endpoint = dataUtilsService.endpointPath(@restPath)
                @socketPathRE = ///^#{@restPath}\/(\w+|\d+)\/.*$///g
                @queryExecutor = new DataQuery(@query)
                # default event handlers
                @onUpdate = angular.noop
                @onNew = angular.noop
                @onChange = angular.noop
                @_new = []
                @_updated = []
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
                    @sendEvents()

            subscribe: ->
                return socketService.subscribe(@socketPath, this)

            close: ->
                return socketService.unsubscribe(@socketPath, this)

            from: (data) ->
                # put items one by one
                @put(i) for i in data
                @recomputeQuery()
                @sendEvents()

            add: (element) ->
                instance = new @WrapperClass(element, @endpoint)
                instance.setAccessor(@accessor)
                @_new.push(instance)
                @push(instance)

            put: (element) ->
                for old in this
                    if old[@id] == element[@id]
                        old.update(element)
                        @_updated.push(old)
                        return
                # if not found, add it.
                @add(element)
            clear: ->
                @pop() while @length > 0

            delete: (element) ->
                index = @indexOf(element)
                if index > -1 then @splice(index, 1)

            recomputeQuery: ->
                @queryExecutor.computeQuery(this)

            sendEvents: ->
                changed = false

                for i in @_new
                    # is it still in the array?
                    if i in this
                        @onNew(i)
                        changed = true

                for i in @_updated
                    # is it still in the array?
                    if i in this
                        @onUpdate(i)
                        changed = true

                if changed
                    @onChange()

                @_new = []
                @_updated = []
