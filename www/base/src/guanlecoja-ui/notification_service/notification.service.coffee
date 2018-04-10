class glNotification extends Service
    constructor: (@$rootScope, @$timeout) ->
        @notifications = []
        @curid = 0
        null

    notify: (opts) ->
        @curid += 1
        opts.title ?= "Info"
        opts.id = @curid
        id = @curid
        if opts.group?
            for i, n of @notifications
                if opts.group == n.group
                    id = i
                    n.msg += "\n" + opts.msg
        if id == @curid
            @notifications.push opts
        null

    # some shortcuts...
    error: (opts) ->
        opts.title ?= "Error"
        @notify(opts)

    network: (opts) ->
        opts.title ?= "Network issue"
        opts.group ?= "Network"
        @notify(opts)

    dismiss: (id) ->
        for i, n of @notifications
            if n.id == id
                @notifications.splice(i, 1)
                return null
        null
