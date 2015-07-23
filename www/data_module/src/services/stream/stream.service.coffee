class Stream extends Factory
    constructor: ->
        return class StreamInstance
            # the unsubscribe listener will be called on each unsubscribe call
            onUnsubscribe: null
            listeners: []

            subscribe: (listener) ->
                if not angular.isFunction(listener)
                    throw new TypeError("Parameter 'listener' must be a function, not #{typeof listener}")

                listener.id = @generateId()
                @listeners.push(listener)

                # unsubscribe
                return =>
                    i = @listeners.indexOf(listener)
                    removed = @listeners.splice(i, 1)
                    # call the unsubscribe listener if it's a function
                    if angular.isFunction(@onUnsubscribe)
                        @onUnsubscribe(listener)

            push: (data) ->
                # call each listener
                listener(data) for listener in @listeners

            destroy: ->
                # @listeners = [], but keep the reference
                @listeners.pop() while @listeners.length > 0

            generateId: ->
                @lastId ?= 0
                return @lastId++
