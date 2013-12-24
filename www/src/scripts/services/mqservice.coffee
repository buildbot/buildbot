angular.module('app').factory 'mqService', ['$http', '$rootScope', ($http, $rootScope) ->
    # private variables
    match = (matcher, value) ->
        # ultra simple matcher used to route event back to the original subscriber
        matcher = new RegExp(matcher.replace("*", "[^/]+"))
        return matcher.test(value)

    listeners = {}
    eventsource = null
    cid = null
    basepath = null

    self =
        # public api
        on: (name, listener, $scope) ->
            namedListeners = listeners[name]
            if !namedListeners or namedListeners.length == 0
                listeners[name] = namedListeners = []
                self.startConsuming(name)
            namedListeners.push(listener)

            # returns unsubscriber
            unsub =  ->
                namedListeners.splice(namedListeners.indexOf(listener), 1)
                if namedListeners.length == 0
                    self.stopConsuming(name)
                    delete listeners[name]
            $scope?.$on("$destroy", unsub)

            return unsub

        broadcast: (eventname, message) ->
            hasmatched = false
            for k, namedListeners of listeners
                if match(k, eventname)
                    for callback in namedListeners
                        callback(message, eventname)
                    hasmatched = true
            if !hasmatched
                throw Error("broadcasting #{eventname} without listeners!")

        # this is intended to be mocked in unittests
        getEventSource: (url) ->
            return new EventSource(url + "listen")

        setBaseUrl: (url) ->
            cid = null
            basepath = url
            eventsource = self.getEventSource(url)
            eventsource.onopen = (e) ->
                cid = null

            eventsource.onerror = (e) ->
                console.error(e)

            eventsource.onmessage = (e) ->
                console.log "got message!", e

            eventsource.addEventListener "handshake", (e) ->
                cid = e.data
                # now we got our handshake, we can start consuming
                # what was registered in between
                # this is still racy, as we can have miss some events during this handshake time
                for k, v of listeners
                    self.startConsuming(k)

            eventsource.addEventListener "event", (e) ->
                e.msg = JSON.parse(e.data)
                $rootScope.$apply ->
                    self.broadcast(e.msg.key, e.msg.message)

        startConsuming: (name) ->
            if cid?
                $http.get(basepath + "add/#{cid}/#{name}")

        stopConsuming: (name) ->
            if cid?
                $http.get(basepath + "remove/#{cid}/#{name}")

    return self
]
