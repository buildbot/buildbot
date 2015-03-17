class MqService extends Factory('common')
    constructor: ($http, $rootScope, $q) ->
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
                return new WebSocket(url)

            setBaseUrl: (url) ->
                pending_msgs = {}
                makedeferred = ->
                    deferred = $q.defer()
                    deferred.promise.then(makedeferred)
                makedeferred()
                ws = self.getWebSocket(url)

                ws.onerror = (e) ->
                    console.error(e)
                    lostConnection = true
                    if navigator.onLine
                        self.setBaseUrl(url)
                    else
                        window.addEventListener "online", ->
                            self.setBaseUrl(url)

                ws.onopen = (e) ->
                    # now we got our handshake, we can start consuming
                    # what was registered in between
                    # this is still racy, as we can have miss some events during this handshake time
                    pending_msgs = {}
                    allp = []
                    for k, v of listeners
                        allp.push(self.startConsuming(k))
                    $q.all(allp).then ->
                        deferred.resolve()
                        # this will trigger bound data to re fetch the full-data
                        if lostConnection
                            $rootScope.$broadcast("lost-sync")

                ws.onmessage = (e) ->
                    msg = JSON.parse(e.data)
                    if msg._id? and pending_msgs[msg._id]?
                        if msg.code != 200
                            pending_msgs[msg._id].reject(msg)
                        else
                            pending_msgs[msg._id].resolve(msg)
                        delete pending_msgs[msg._id]
                    else
                        $rootScope.$apply ->
                            self.broadcast(msg.key, msg.message)
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
