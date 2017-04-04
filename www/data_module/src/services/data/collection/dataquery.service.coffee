class DataQuery extends Factory
    constructor: ($http, $q, API) ->
        return class DataQueryClass
            constructor: (query = {}) ->
                @query = query
                @filters = {}
                for fieldAndOperator, value of query
                    if ['field', 'limit', 'offset', 'order', 'property'].indexOf(fieldAndOperator) < 0
                        if ['on', 'true', 'yes'].indexOf(value) > -1 then value = true
                        else if ['off', 'false', 'no'].indexOf(value) > -1 then value = false
                        @filters[fieldAndOperator] = value

            computeQuery: (array) ->
                # 1. filtering
                @filter(array)

                # 2. sorting
                order = @query?.order
                @sort(array, order)

                # 3. limit
                limit = @query?.limit
                @limit(array, limit)


            isFiltered: (v) ->
                cmp = false
                for fieldAndOperator, value of @filters
                    [field, operator] = fieldAndOperator.split('__')
                    switch operator
                        when 'ne' then cmp = v[field] != value
                        when 'lt' then cmp = v[field] <  value
                        when 'le' then cmp = v[field] <= value
                        when 'gt' then cmp = v[field] >  value
                        when 'ge' then cmp = v[field] >= value
                        else cmp = v[field] == value or
                            (angular.isArray(v[field]) and value in v[field]) or
                            # private fields added by the data service
                            v["_#{field}"] == value or
                            (angular.isArray(v["_#{field}"]) and value in v["_#{field}"])
                    if !cmp then return false
                 return true

            filter: (array) ->
                i = 0
                while i < array.length
                    v = array[i]
                    if @isFiltered(v)
                        i += 1
                    else
                        array.splice(i, 1)

            sort: (array, order) ->
                compare = (property) ->
                    reverse = false
                    if property[0] is '-'
                        property = property[1..]
                        reverse = true

                    return (a, b) ->
                        if reverse then [a, b] = [b, a]

                        if a[property] < b[property] then -1
                        else if a[property] > b[property] then 1
                        else 0
                if angular.isString(order)
                    array.sort compare(order)
                else if angular.isArray(order)
                    array.sort (a, b) ->
                        for o in order
                            f = compare(o)(a, b)
                            if f then return f
                        return 0

            limit: (array, limit) ->
                while array.length > limit
                    array.pop()
