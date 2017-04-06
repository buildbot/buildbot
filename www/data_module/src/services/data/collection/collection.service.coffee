class Collection extends Factory
    constructor: ($q, $injector, $log, dataUtilsService, socketService, DataQuery, $timeout) ->
        angular.isArray = Array.isArray = (arg) ->
            return arg instanceof Array
        return class CollectionInstance extends Array
            constructor: (@restPath, @query = {}, @accessor) ->
                @socketPath = dataUtilsService.socketPath(@restPath)
                @type = dataUtilsService.type(@restPath)
                @id = dataUtilsService.classId(@restPath)
                @endpoint = dataUtilsService.endpointPath(@restPath)
                @socketPathRE = dataUtilsService.socketPathRE(@socketPath)
                @queryExecutor = new DataQuery(@query)
                # default event handlers
                @onUpdate = angular.noop
                @onNew = angular.noop
                @onChange = angular.noop
                @_new = []
                @_updated = []
                @_byId = {}
                @$resolved = false
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

            then: (callback) ->
                console.log "Should not use collection as a promise. Callback will be called several times!"
                @onChange = callback

            getArray: ->
                console.log "getArray() is deprecated. dataService.get() directly returns the collection!"
                return this

            get: (id) ->
                return @_byId[id]

            hasOwnProperty: (id) ->
                return @_byId.hasOwnProperty(id)

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

            initial: (data) ->
                @$resolved = true
                # put items one by one if not already in the array
                # if they are that means they come from an update event
                # the event is always considered the latest data
                # so we don't overwrite it with REST data
                for i in data
                    if not @hasOwnProperty(i[@id])
                        @put(i)
                @recomputeQuery()
                @sendEvents(initial:true)

            from: (data) ->
                # put items one by one
                @put(i) for i in data
                @recomputeQuery()
                @sendEvents()

            item: (i) ->
                return this[i]

            add: (element) ->
                # don't create wrapper if element is filtered
                if @queryExecutor.filter([element]).length == 0
                    return
                instance = new @WrapperClass(element, @endpoint)
                instance.setAccessor(@accessor)
                instance.$collection = this
                @_new.push(instance)
                @_byId[instance[@id]] = instance
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

            sendEvents: (opts)->
                # send the events asynchronously
                _new = @_new
                _updated = @_updated
                @_updated = []
                @_new = []
                $timeout =>
                    changed = false
                    for i in _new
                        # is it still in the array?
                        if i in this
                            @onNew(i)
                            changed = true

                    for i in _updated
                        # is it still in the array?
                        if i in this
                            @onUpdate(i)
                            changed = true

                    if changed or opts?.initial
                        @onChange(this)
                , 0
