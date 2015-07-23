class DataUtils extends Service
    constructor: ->
        return new class DataUtils
            constructor: ->

            # capitalize first word
            capitalize: (w) ->
                w[0].toUpperCase() + w[1..-1].toLowerCase()

            # returns the type of the endpoint
            type: (e) ->
                splitted = e.split('/')
                while true
                    name = splitted.pop()
                    parsed = parseInt(name)
                    break if splitted.length is 0 or not (angular.isNumber(parsed) and not isNaN(parsed))
                return name

            # singularize the type name
            singularType: (e) ->
                @type(e).replace(/s$/, '')

            # id of the type
            classId: (e) ->
                 @singularType(e) + 'id'

            # capitalized type name
            className: (e) ->
                @capitalize(@singularType(e))

            socketPath: (args) ->
                # if the argument count is even, the last argument is an id
                stars = ['*']
                # is it odd?
                if args.length % 2 is 1
                    stars.push('*')
                args.concat(stars).join('/')

            restPath: (args) ->
                args.slice().join('/')

            endpointPath: (args) ->
                # if the argument count is even, the last argument is an id
                argsCopy = args.slice()
                # is it even?
                if argsCopy.length % 2 is 0
                    argsCopy.pop()
                argsCopy.join('/')
