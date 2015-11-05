class fakeTabex extends Service
    constructor: ($log, $q, $rootScope, $timeout) ->
        return new class FakeTabexService
            channels: {}
            CHANNELS =
                MASTER: '!sys.master'
                REFRESH: '!sys.channels.refresh'

            on: (c, l) ->
                if c == CHANNELS.MASTER
                    $timeout((-> l({node_id: 1, master_id: 1})), 1)
                @channels[c] ?= []
                @channels[c].push(l)
                @emit CHANNELS.REFRESH, {channels: Object.keys(@channels)}, true

            off: (c, l) ->
                if angular.isArray(@channels[c])
                    idx = @channels[c].indexOf(l)
                    if idx > -1 then @channels[c].split(idx, 1)

            emit: (c, m, self = false) ->
                if angular.isArray(@channels[c]) and self
                    for l in @channels[c]
                        if angular.isFunction(l) then l(m)
