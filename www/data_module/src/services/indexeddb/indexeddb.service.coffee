class IndexedDB extends Service
    constructor: ($log, $injector, $q, $window, config, $timeout, dataUtilsService, DBSTORES, SPECIFICATION) ->
        return new class IndexedDBService
            constructor: ->
                # config.enableIndexedDB = true
                @db = new $window.Dexie('BBCache')
                version = $window.localStorage.getItem('BBCacheVERSION')
                # just recreate in case of old version in the browser
                if version != SPECIFICATION.VERSION
                    @db.delete()
                    @db = new $window.Dexie('BBCache')
                stores = {}
                angular.extend stores, @processSpecification(SPECIFICATION), DBSTORES
                @db.version(1).stores(stores)
                # global db error handler
                @db.on 'error', (e) -> $log.error(e)
                # open the database
                @open()
                $window.localStorage.setItem('BBCacheVERSION', SPECIFICATION.VERSION)

                @spentInDb = []
                @cache = {}

            logSpentInDb: ->
                tot = 0
                for i in @spentInDb
                    tot += i
                $log.debug "spent in indexedDB: ", tot, "num queries:", @spentInDb.length
                @spentInDb = []

            open: ->
                $q (resolve) =>
                    @db.open()
                    .catch (e) -> $log.error 'indexedDBService: open', e
                    .finally -> resolve()

            clear: ->
                $q (resolve) =>
                    @db.delete()
                    .catch (e) -> $log.error 'indexedDBService: clear', e
                    .finally => @open().then -> resolve()

            getTable: (tableName) ->
                table = @db[tableName]
                @cache[table.name] ?= {}
                table.cache  = @cache[table.name]
                return table

            put: (table, value) ->
                table = @getTable(table)
                if config.enableIndexedDB
                    element = { }
                    for k, v of value
                        if not angular.isObject(v)
                            element[k] = angular.toJson(v)
                    return table.put(element)
                else
                    table.cache[value[table.schema.primKey.keyPath]] = value
                    return $q.when()

            getObject: (table, id) ->
                table = @getTable(table)
                if config.enableIndexedDB
                    return table.get(id)
                if not table.cache.hasOwnProperty(id)
                    table.cache[id] = {}

                return $q.when(table.cache[id])

            get: (url, query = {}) ->
                $q (resolve, reject) =>
                    @processUrl(url).then ([tableName, q, id]) =>
                        angular.extend query, q

                        if not SPECIFICATION[tableName]?
                            resolve([])
                            return
                        table = @getTable(tableName)

                        t1 = window.performance.now()
                        if @logSpentInDbTimeout?
                            $timeout.cancel @logSpentInDbTimeout
                        @logSpentInDbTimeout = $timeout ( => @logSpentInDb()), 2000

                        # convert promise to $q implementation
                        if id?
                            @getObject(tableName, id).then (e) ->
                                resolve(dataUtilsService.parse(e))
                            return

                        @native_filter(table, query).then ([array, query]) =>
                            t2 = window.performance.now()
                            @spentInDb .push t2 - t1
                            # 1. filtering
                            filters = []
                            for fieldAndOperator, value of query
                                if ['field', 'limit', 'offset', 'order'].indexOf(fieldAndOperator) < 0
                                    filters[fieldAndOperator] = value
                            array = @filter(array, filters, tableName)

                            # 2. sorting
                            order = query?.order
                            array = @sort(array, order)

                            # 3. pagination
                            offset = query?.offset
                            limit = query?.limit
                            array = @paginate(array, offset, limit)

                            # TODO 4. properties
                            property = query?.property
                            array = @properties(array, property)

                            # 5. fields
                            fields = query?.field
                            array = @fields(array, fields)

                            resolve(array)
            dataoperator2dexie: {
                'eq': 'equals'
                'ne': 'notEqual'
                'lt': 'bellow'
                'le': 'bellowOrEqual'
                'gt': 'above'
                'ge': 'aboveOrEqual'
            }
            table_has_index: (table, field) ->
                for index in table.schema.indexes
                    if index.keyPath == field
                        return true
                return false

            native_filter: (table, query) ->
                if not config.enableIndexedDB
                    return $.when([_.values(table.cache), query])

                $q (resolve, reject) =>
                    query_remain = angular.extend({}, query)
                    collection = table
                    for fieldAndOperator, value of query
                        if ['field', 'limit', 'offset', 'order'].indexOf(fieldAndOperator) >= 0
                            continue

                        [field, operator] = fieldAndOperator.split('__')
                        if not operator?
                            operator = 'eq'
                        dexie_operator = @dataoperator2dexie[operator]
                        if not dexie_operator
                            continue
                        if ['on', 'true', 'yes'].indexOf(value) > -1 then value = true
                        else if ['off', 'false', 'no'].indexOf(value) > -1 then value = false

                        if @table_has_index(table, field)
                            if collection.where(field)[dexie_operator]?
                                collection = collection.where(field)[dexie_operator](value)
                                delete query_remain[fieldAndOperator]
                                break  # can only do one native filter
                    collection.toArray().then (array) ->
                        array = array.map (e) -> dataUtilsService.parse(e)
                        resolve [array, query_remain]

            filter: (array, filters, tableName) ->
                array.filter (v) ->
                    for fieldAndOperator, value of filters
                        if ['on', 'true', 'yes'].indexOf(value) > -1 then value = true
                        else if ['off', 'false', 'no'].indexOf(value) > -1 then value = false
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

            sort: (array, order) ->
                compare = (property) ->
                    if property[0] is '-'
                        property = property[1..]
                        reverse = true

                    return (a, b) ->
                        if reverse then [a, b] = [b, a]

                        if a[property] < b[property] then -1
                        else if a[property] > b[property] then 1
                        else 0

                copy = array[..]
                if angular.isString(order)
                    copy.sort compare(order)
                else if angular.isArray(order)
                    copy.sort (a, b) ->
                        for o in order
                            f = compare(o)(a, b)
                            if f then return f
                        return 0

                return copy

            paginate: (array, offset, limit) ->
                offset ?= 0
                if offset >= array.length
                    return []

                if not limit? or offset + limit > array.length
                    end = array.length
                else
                    end = offset + limit - 1

                return array[offset..end]

            # TODO
            properties: (array, properties) ->
                return array

            fields: (array, fields) ->
                if not fields?
                    return array

                if not angular.isArray(fields) then fields = [fields]

                for element in array
                    for key of element
                        if key not in fields
                            delete element[key]

                return array

            processUrl: (url) ->
                $q (resolve, reject) =>
                    [root, id, path...] = url.split('/')
                    specification = SPECIFICATION[root]
                    query = {}
                    if path.length == 0
                        id = dataUtilsService.numberOrString(id)
                        if angular.isString(id) and specification.identifier
                            query[specification.identifier] = id
                            id = null
                        resolve [root, query, id]
                        return

                    pathString = path.join('/')
                    match = specification.paths.filter (p) ->
                        replaced = p
                            .replace ///#{SPECIFICATION.FIELDTYPES.IDENTIFIER}\:\w+///g, '[a-zA-Z]+'
                            .replace ///#{SPECIFICATION.FIELDTYPES.NUMBER}\:\w+///g, '\\d+'
                        ///^#{replaced}$///.test(pathString)
                    .pop()
                    if not match?
                        throw new Error("No child path (#{path.join('/')}) found for root (#{root})")

                    match = match.split('/')

                    if path.length % 2 is 0
                        fieldValue = dataUtilsService.numberOrString path.pop()
                        [fieldType, fieldName] = match.pop().split(':')
                    tableName = path.pop()
                    match.pop()
                    parentFieldValue = dataUtilsService.numberOrString(path.pop() or id)
                    parentFieldName = match.pop()?.split(':').pop() or SPECIFICATION[root].id
                    parentName = match.pop() or root
                    parentId = SPECIFICATION[parentName].id

                    if fieldName is SPECIFICATION[tableName]?.id
                        id = fieldValue
                        resolve [tableName, query, id]
                    else
                        if parentFieldName isnt parentId
                            splitted = url.split('/')
                            nextUrl = splitted[...(if splitted.length % 2 == 0 then -2 else -1)].join('/')
                            @get(nextUrl).then (array) ->
                                query[parentId] = array[0][parentId]
                                if fieldName? then query[fieldName] = fieldValue
                                resolve [tableName, query, null]
                        else
                            query[parentFieldName] = parentFieldValue
                            if fieldName? then query[fieldName] = fieldValue
                            resolve [tableName, query, null]

            processSpecification: (specification) ->
                # IndexedDB tables
                stores = {}
                for name, s of specification
                    if angular.isArray(s.fields)
                        dbfields = []
                        hasid = false
                        for field in s.fields[..]
                            # create primary key for id field
                            if s.id == field
                                dbfields.push "&#{field}"
                                hasid = true
                            # create index multiple key for fields ending with id
                            else if _.endsWith(field, "id")
                                dbfields.push "*#{field}"
                            else
                                dbfields.push field
                        if not hasid
                            dbfields.unshift('++id')
                        stores[name] = dbfields.join(',')
                return stores
