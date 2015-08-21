class Tabex extends Service
    constructor: ($log, $window, $q, $timeout, socketService, restService, dataUtilsService, indexedDBService, SPECIFICATION) ->
        return new class TabexService
            CHANNELS =
                MASTER: '!sys.master'
                REFRESH: '!sys.channels.refresh'

            ROLES =
                MASTER: 'bb.role.master'
                SLAVE: 'bb.role.slave'
            _ROLES: ROLES # used in testing

            EVENTS =
                READY: 'bb.event.ready'
                UPDATE: 'bb.event.update'
                NEW: 'bb.event.new'
            EVENTS: EVENTS

            client: $window.tabex.client()

            constructor: ->
                # the message handler will be called on update messages
                socketService.onMessage = @messageHandler
                # the close handler will be called on close event
                # we need to resend the startConsuming messages for
                # every tracked channels
                socketService.onClose = @closeHandler

                @initialRoleDeferred = $q.defer()
                @initialRole = @initialRoleDeferred.promise

                @client.on CHANNELS.MASTER, @masterHandler
                @client.on CHANNELS.REFRESH, @refreshHandler

                $window.onunload = $window.onbeforeunload = (e) =>
                    @activatePaths()
                    return null

            getSpecification: (type) -> SPECIFICATION[type]

            masterHandler: (data) =>
                # the master handles the data requests and the WebSocket connection
                if data.node_id is data.master_id
                    @role = ROLES.MASTER
                    @initialRoleDeferred.resolve()
                    socketService.open()
                else
                    @role = ROLES.SLAVE
                    @initialRoleDeferred.resolve()
                    # close the WebSocket connection if it's open
                    socketService.close()

            refreshHandler: (data) =>
                # wait for the role to be determined
                @initialRole.then =>
                    if @role is ROLES.MASTER then @masterRefreshHandler(data)

            debounceTimeout: 100
            # path: [query]
            trackedPaths: {}
            # consumed paths
            consuming: {}
            masterRefreshHandler: (data) ->
                # debounce logic
                if @timeoutPromise? then $timeout.cancel(@timeoutPromise)
                @timeoutPromise = $timeout =>
                    @activatePaths().then =>

                        # filter channels by system channels (starts with `!sys.`)
                        channels = data.channels.filter (c) -> c.indexOf('!sys.') != 0

                        paths = {}
                        for channel in channels
                            try
                                r = angular.fromJson(channel)
                                paths[r.path] ?= []
                                paths[r.path].push(r.query)
                            catch e
                                $log.error('channel is not a JSON string', channel)
                                return

                        @startConsumingAll(paths).then =>
                            # send stopConsuming messages after we get response
                            # for startConsuming messages, therefore no update
                            # will be lost
                            for path of @consuming
                                if path not of paths
                                    # unsubscribe removed paths
                                    @stopConsuming(path)
                                    delete @consuming[path]

                            @trackedPaths = paths
                            # load all tracked path into cache
                            @loadAll(paths)

                , @debounceTimeout

            messageHandler: (key, message) =>
                # ../type/id/event
                [type, id, event] = key.split('/')[-3..]
                # translate the event type
                if event is 'new' then event = EVENTS.NEW
                else event = EVENTS.UPDATE
                # update the object in the db
                indexedDBService.db[type].put(message).then =>
                    # emit the event
                    for path of @trackedPaths
                        if ///^#{path.replace(/\*/g, '(\\w+|\\d+)')}$///.test(key)
                            for query in @trackedPaths[path]
                                @emit path, query, event

            closeHandler: =>
                paths = angular.copy(@trackedPaths)
                @trackedPaths = {}
                @startConsumingAll(paths)

            loadAll: (paths) ->
                db = indexedDBService.db
                db.paths.toArray().then (dbPaths) =>
                    for path, queries of paths
                        for query in queries
                            @load(path, query, dbPaths)

            load: (path, query, dbPaths = []) ->
                $q (resolve, reject) =>
                    db = indexedDBService.db

                    t = dataUtilsService.type(path)
                    specification = @getSpecification(t)
                    # test if cached and active
                    for dbPath in dbPaths
                        dbPath.query = angular.fromJson(dbPath.query)
                        inCache =
                            (dbPath.path is path and
                            (angular.equals(dbPath.query, query) or angular.equals(dbPath.query, {}))) or
                            (dbPath.path is t and angular.equals(dbPath.query, {}))
                        elapsed = new Date() - new Date(dbPath.lastActive)
                        active = elapsed < 2000 or specification.static == true

                        if inCache and active
                            resolve()
                            return

                    restPath = dataUtilsService.restPath(path)
                    [parentName, parentId] = @getParent(restPath)
                    parentIdName = SPECIFICATION[parentName]?.id
                    if parentIdName? then parentIdName = "_#{parentIdName}"
                    restService.get(restPath, query).then (data) =>
                        type = dataUtilsService.type(restPath)
                        data = dataUtilsService.unWrap(data, type)
                        db.transaction 'rw', db[type], ->
                            if not angular.isArray(data) then data = [data]
                            data.forEach (i) ->
                                put = (element) ->
                                    for k, v of element
                                        if angular.isObject(element[k])
                                            element[k] = angular.toJson(v)
                                    db[type].put(element)

                                idName = SPECIFICATION[type]?.id
                                id = i[idName]
                                if id?
                                    db[type].get(id).then (e) ->
                                        e = dataUtilsService.parse(e)
                                        for k, v of i then e[k] = v
                                        if parentIdName?
                                            e[parentIdName] ?= []
                                            if parentId not in e[parentIdName]
                                                e[parentIdName].push(parentId)
                                        put(e)
                                    .catch ->
                                        if parentIdName? then i[parentIdName] = [parentId]
                                        put(i)
                                else
                                    if parentIdName? then i[parentIdName] = [parentId]
                                    put(i)

                        .then ->
                            db.transaction 'rw', db.paths, ->
                                # cached path informations
                                db.paths.put {
                                    path: path
                                    query: angular.toJson(query)
                                }
                            .then -> resolve()
                            .catch (error) -> reject(error)
                        .catch (error) -> reject(error)
                    , (error) -> reject(error)

                .then =>
                    @emit path, query, EVENTS.READY
                , (error) =>
                    $log.error(error)

            getParent: (restPath) ->
                path = restPath.split('/')
                if path % 2 == 0 then path.pop()
                path.pop()
                id = dataUtilsService.numberOrString path.pop()
                name = path.pop()
                return [name, id]

            activatePaths: ->
                paths = angular.copy(@trackedPaths)
                db = indexedDBService.db
                db.transaction 'rw', db.paths, =>
                    now = (new Date()).toString()
                    for path, queries of paths
                        for query in queries
                            db.paths
                            .where('[path+query]').equals([path,angular.toJson(query)])
                            .modify('lastActive': now)

            on: (options..., listener) ->
                [path, query] = options
                query = angular.copy(query) or {}
                subscribe = query.subscribe
                delete query.subscribe
                # if subscribe is false, we just load the data
                if subscribe == false
                    indexedDBService.db.paths.toArray().then (dbPaths) =>
                        @load(path, query, dbPaths).then -> listener(EVENTS.READY)
                    return
                # if subscribe is true, we subscribe on events
                channel =
                    path: path
                    query: query
                @client.on angular.toJson(channel), listener

            off: (options..., listener) ->
                [path, query] = options
                query = angular.copy(query) or {}
                delete query.subscribe

                channel =
                    path: path
                    query: query
                @client.off angular.toJson(channel), listener

            emit: (options..., message) ->
                [path, query] = options
                channel =
                    path: path
                    query: query or {}
                @client.emit angular.toJson(channel), message, true

            startConsuming: (path) ->
                socketService.send
                    cmd: 'startConsuming'
                    path: path

            stopConsuming: (path) ->
                socketService.send
                    cmd: 'stopConsuming'
                    path: path

            startConsumingAll: (paths) ->
                if angular.isArray(paths)
                    socketPaths = paths[...]
                else if angular.isObject(paths)
                    socketPaths = Object.keys(paths)
                else throw new Error('Parameter paths is not an object or an array')

                # filter socket paths that are included in another paths
                pathsToRemove = []
                for p, i in socketPaths
                    r = ///^#{p.replace(/\*/g, '(\\w+|\\d+|\\*)')}$///
                    for q, j in socketPaths
                        if j != i and r.test(q) then pathsToRemove.push(q)
                for p in pathsToRemove
                    socketPaths.splice socketPaths.indexOf(p), 1

                promises = []
                for path in socketPaths
                    if path not of @trackedPaths
                        @consuming[path] = true
                        promises.push @startConsuming(path)

                return $q.all(promises)

            mergePaths: (dest, src) ->
                for path, queries of src
                    dest[path] ?= []
                    for query in queries
                        if dest[path].filter (e) ->
                            angular.equals(e, query)
                        .length == 0
                            dest[path].push(query)
