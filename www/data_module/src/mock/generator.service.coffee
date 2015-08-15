# types for generating test data: null, number, string, boolean, timestamp, <array>[], <object>, <objectName in Specification>
class Generator extends Service
    self = null
    constructor: ->
        self = @

    number: (min = 0, max = 100) ->
        random = Math.random() * (max - min) + min
        Math.floor(random)

    ids: {}
    id: (name = '') ->
        self.ids[name] ?= 0
        self.ids[name]++

    boolean: -> Math.random() < 0.5

    timestamp: (after = Date.now()) ->
        date = new Date(after + self.number(1, 1000000))
        Math.floor(date.getTime() / 1000)

    string: (length) ->
        if length? then length++
        self.number(100, Number.MAX_VALUE).toString(36).substring(0, length)

    array: (fn, args...) ->
        times = self.number(1, 10)
        array = []
        for i in [1..times]
            array.push fn(args...)
        return array
