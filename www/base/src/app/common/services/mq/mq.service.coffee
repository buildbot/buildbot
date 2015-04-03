class MqService extends Factory('common')
    constructor: ($http, $rootScope, $q, bbSettingsService) ->
        # private variables
        match = (matcher, value) ->
            # ultra simple matcher used to route event back to the original subscriber
            matcher = new RegExp("^"+matcher.replace(/\*/g, "[^/]+") + "$")
            return matcher.test(value)
        listeners = {}
        ws = null
        curid = 1
        pending_msgs = {}
        deferred = null
        lostConnection = false
        listening = false
        settings = bbSettingsService.getSettingsGroup("Websockets")
        self =
            # tested internal api
            _match: match

            # public api
            on: (name, listener, $scope) ->
                namedListeners = listeners[name]
                if !namedListeners or namedListeners.length == 0
                    listeners[name] = namedListeners = []
                    p = self.startConsuming(name)
                else
                    p = $q.when(0)
                namedListeners.push(listener)

                # returns unsubscriber
                unsub =  ->
                    namedListeners.splice(namedListeners.indexOf(listener), 1)
                    if namedListeners.length == 0
                        p = self.stopConsuming(name)
                        delete listeners[name]
                    else
                        p = $q.when(0)
                    return p
                $scope?.$on("$destroy", unsub)
                return p.then -> unsub

            broadcast: (eventname, message) ->
                hasmatched = false
                if _.isArray(eventname)
                    eventname = eventname.join("/")
                for k, namedListeners of listeners
                    if match(k, eventname)
                        for callback in namedListeners
                            callback(message, eventname)
                        hasmatched = true
                if !hasmatched
                    for k, namedListeners of listeners
                        console.log k, eventname
                    throw Error("broadcasting #{eventname} without listeners!")

            # this is intended to be mocked in unittests
            getWebSocket: (url) ->
                # we use reconnecting websocket for automatic reconnection
                return new ReconnectingWebSocket(url)

            maybeClose: ->
                if document.hidden and listening
                    if ws.debug
                        console.log "Tab hidden, stop listening"
                        console.log "listeners:", listeners
                    listening = false
                    ws.maxReconnectAttempts = 1
                    maybereopen = ->
                        if not document.hidden
                            listening = true
                            document.removeEventListener("visibilitychange", maybereopen)
                            ws.maxReconnectAttempts = 0
                            ws.open(true)
                    document.addEventListener("visibilitychange", maybereopen)
                    return true
                return false
            setBaseUrl: (url) ->
                pending_msgs = {}
                makedeferred = ->
                    deferred = $q.defer()
                    deferred.promise.then(makedeferred)
                makedeferred()

                ws = self.getWebSocket(url)
                ws.debug = settings.debug_websockets.value
                listening = true
                ws.onerror = (e) -> $rootScope.$apply ->
                    self.maybeClose()
                ws.onclose = (e) -> $rootScope.$apply ->
                    self.maybeClose()
                    # forget all listeners, they will register back when connection is restored
                    $rootScope.$broadcast("mq.lost_connection", e)
                    lostConnection = true
                    listeners = {}

                ws.onopen = (e) -> $rootScope.$apply ->
                    pending_msgs = {}
                    allp = []
                    for k, v of listeners
                        allp.push(self.startConsuming(k))

                    $q.all(allp).then ->
                        deferred.resolve()
                        if lostConnection
                            # this will trigger bound data to re fetch the full-data
                            $rootScope.$broadcast("mq.restored_connection", e)
                        else
                            $rootScope.$broadcast("mq.first_connection", e)

                ws.onmessage = (e) ->  $rootScope.$apply ->
                    msg = JSON.parse(e.data)
                    if msg._id? and pending_msgs[msg._id]?
                        if msg.code != 200
                            pending_msgs[msg._id].reject(msg)
                        else
                            pending_msgs[msg._id].resolve(msg)
                        delete pending_msgs[msg._id]
                    else if msg.k? and msg.m?
                        self.broadcast(msg.k, msg.m)
                    else
                        $rootScope.$broadcast("mq.unkown_msg", msg)

            sendMessage: (args) ->
                curid += 1
                args._id = curid
                d = $q.defer()
                d.promise._id = curid
                pending_msgs[curid] = d
                ws.send(JSON.stringify(args))
                return d.promise

            startConsuming: (path) ->
                if ws.readyState == 1
                    return self.sendMessage(cmd:"startConsuming", path:path)
                else
                    return deferred.promise
            stopConsuming: (path) ->
                if ws.readyState == 1
                    return self.sendMessage(cmd:"stopConsuming", path:path)

        return self

class State extends Config
    constructor: (bbSettingsServiceProvider) ->

        bbSettingsServiceProvider.addSettingsGroup
            name:'Websockets'
            caption: 'Websocket'
            items:[
                type:'bool'
                name:'debug_websockets'
                caption:'Debug Websockets'
                default_value: false
            ]
