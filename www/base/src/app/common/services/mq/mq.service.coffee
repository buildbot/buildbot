    class MqService extends Factory('common')
        constructor: ($http, $rootScope, $q) ->
            # private variables
    hidden='undefined'
    state='undefined'
    visibilityChange='undefined'

            if typeof document.hidden != 'undefined'
              hidden = 'hidden'
              visibilityChange = 'visibilitychange'
              state = 'visibilityState'
            else if typeof document.mozHidden != 'undefined'
              hidden = 'mozHidden'
              visibilityChange = 'mozvisibilitychange'
              state = 'mozVisibilityState'
            else if typeof document.msHidden != 'undefined'
              hidden = 'msHidden'
              visibilityChange = 'msvisibilitychange'
              state = 'msVisibilityState'
            else if typeof document.webkitHidden != 'undefined'
              hidden = 'webkitHidden'
              visibilityChange = 'webkitvisibilitychange'
              state = 'webkitVisibilityState'
              
            match = (matcher, value) ->
                # ultra simple matcher used to route event back to the original subscriber
                matcher = new RegExp("^"+matcher.replace(/\*/g, "[^/]+") + "$")
                return matcher.test(value)

            listeners = {}
            eventsource = null
            cid = null
            basepath = null
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
                            self.stopConsuming(name)
                            delete listeners[name]
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
                getEventSource: (url) ->
                    return new EventSource(url + "listen")

                setBaseUrl: (url) ->
                    cid = null
                    makedeferred = ->
                        deferred = $q.defer()
                        deferred.promise.then(makedeferred)
                    makedeferred()
                    basepath = url
                    eventsource = self.getEventSource(url)
                    eventsource.onopen = (e) ->
                        cid = null

                    eventsource.onerror = (e) ->
                        console.error(e)
                        lostConnection = true
                    eventsource.onmessage = (e) ->
                        console.log "got message!", e

                    document.addEventListener visibilityChange, (->
                      if document[state] = 'hidden'
                        eventsource.close()
                      else
                        self.startConsuming name
                      return
                      ), false


                    eventsource.addEventListener "handshake", (e) ->
                        cid = e.data
                        # now we got our handshake, we can start consuming
                        # what was registered in between
                        # this is still racy, as we can have miss some events during this handshake time
                        allp = []
                        for k, v of listeners
                            allp.push(self.startConsuming(k))
                        $q.all(allp).then ->
                            deferred.resolve()
                            # this will trigger bound data to re fetch the full-data
                            if lostConnection
                                $rootScope.$broadcast("lost-sync")

                    eventsource.addEventListener "event", (e) ->
                        e.msg = JSON.parse(e.data)
                        $rootScope.$apply ->
                            self.broadcast(e.msg.key, e.msg.message)

                startConsuming: (name) ->
                    if cid?
                        return $http.get(basepath + "add/#{cid}/#{name}")
                    else
                        return deferred.promise
                stopConsuming: (name) ->
                    if cid?
                        $http.get(basepath + "remove/#{cid}/#{name}")

            return self
