class DataUtils extends Service
    constructor: (SPECIFICATION) ->
        return new class dataUtilsService
            # capitalize first word
            capitalize: (string) ->
                string[0].toUpperCase() + string[1..].toLowerCase()

            # returns the type of the endpoint
            type: (arg) ->
                a = @copyOrSplit(arg)
                a = a.filter (e) -> e isnt '*'
                # if the argument count is even, the last argument is an id
                if a.length % 2 is 0 then a.pop()
                a.pop()

            # singularize the type name
            singularType: (arg) ->
                @type(arg).replace(/s$/, '')

            socketPath: (arg) ->
                a = @copyOrSplit(arg)
                # if the argument count is even, the last argument is an id
                stars = ['*']
                # is it odd?
                if a.length % 2 is 1 then stars.push('*')
                a.concat(stars).join('/')

            restPath: (arg) ->
                a = @copyOrSplit(arg)
                a = a.filter (e) -> e isnt '*'
                a.join('/')

            endpointPath: (arg) ->
                # if the argument count is even, the last argument is an id
                a = @copyOrSplit(arg)
                a = a.filter (e) -> e isnt '*'
                # is it even?
                if a.length % 2 is 0 then a.pop()
                a.join('/')

            copyOrSplit: (arrayOrString) ->
                if angular.isArray(arrayOrString)
                    # return a copy
                    arrayOrString[..]
                else if angular.isString(arrayOrString)
                    # split the string to get an array
                    arrayOrString.split('/')
                else
                    throw new TypeError("Parameter 'arrayOrString' must be a array or a string, not #{typeof arrayOrString}")

            unWrap: (data, path) ->
                type = @type(path)
                type = SPECIFICATION[type]?.restField or type
                data[type]

            parse: (object) ->
                for k, v of object
                    try
                        object[k] = angular.fromJson(v)
                    catch error then # ignore
                return object

            numberOrString: (str = null) ->
                # if already a number
                if angular.isNumber(str) then return str
                # else parse string to integer
                number = parseInt str, 10
                if !isNaN(number) then number else str

            emailInString: (string) ->
                if not angular.isString(string)
                    throw new TypeError("Parameter 'string' must be a string, not #{typeof string}")
                emailRegex = /[a-zA-Z0-9.!#$%&'*+/=?^_`{|}~-]+@[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)*/
                emailRegex.exec(string).pop() or ''
