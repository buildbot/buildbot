window.mockEventSource = ->
    mocked = (url) ->
        class EventSourceMock

            constructor: (@url) ->
                this.readyState = 1  # directly connect
                this.onEvent = {}

            addEventListener: (event, cb) ->
                if not this.onEvent.hasOwnProperty(event)
                    this.onEvent[event] = []
                this.onEvent[event].push(cb)

            fakeEvent: (eventtype, event) ->
                if this.onEvent.hasOwnProperty(eventtype)
                    for cb in this.onEvent[eventtype]
                        cb(event)

            close: ->
                this.readyState = 2

        return new EventSourceMock(url)

    # overrride "EventSource"
    beforeEach module(($provide) ->
        $provide.value("EventSource", mocked)
        null  # those module callbacks need to return null!
    )
