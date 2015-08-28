describe 'IndexedDB service', ->
    beforeEach module 'bbData'
    beforeEach module ($provide) ->
        specification =
            FIELDTYPES:
                IDENTIFIER: 'i'
                NUMBER: 'n'

            typeA:
                id: 'idA'
                paths: [
                    'typeB'
                    'typeB/i:idB'
                    'typeB/i:idB/typeC'
                    'typeB/i:idB/typeC/i:stringC'
                    'typeB/i:idB/typeC/n:numberC'
                    'typeC'
                ]

            typeB:
                id: 'idB'
                paths: [
                    'typeC'
                    'typeC/n:idC'
                    'typeC/i:stringC'
                ]

            typeC:
                id: 'idC'
                identifier: 'stringC'
                paths: []
        $provide.constant 'SPECIFICATION', specification

    indexedDBService = testArray = $rootScope = db = dbMock = undefined
    injected = ($injector) ->
        indexedDBService = $injector.get('indexedDBService')
        $rootScope = $injector.get('$rootScope')

        fn = null
        promise =
          then: (fn) ->
              fn()
              promise
          catch: (fn) ->
              fn('error')
              promise
          finally: (fn) ->
              fn()
              promise
        dbMock =
            open: jasmine.createSpy('open').and.returnValue(promise)
            delete: jasmine.createSpy('delete').and.returnValue(promise)

        testArray = [
                builderid: 1
                buildid: 3
                buildrequestid: 1
                complete: false
                complete_at: null
                started_at: 1417802797
            ,
                builderid: 2
                buildid: 1
                buildrequestid: 1
                complete: true
                complete_at: 1417803429
                started_at: 1417803026
            ,
                builderid: 1
                buildid: 2
                buildrequestid: 1
                complete: true
                complete_at: 1417803038
                started_at: 1417803025
          ]

    beforeEach(inject(injected))

    it 'should be defined', ->
        expect(indexedDBService).toBeDefined()

    describe 'open()', ->

        it 'should open the db and return a promise', ->
            db = indexedDBService.db
            indexedDBService.db = dbMock
            callback = jasmine.createSpy('cb')
            indexedDBService.open().then(callback)
            expect(callback).not.toHaveBeenCalled()
            $rootScope.$apply()
            expect(callback).toHaveBeenCalled()
            indexedDBService.db = db

    describe 'clear()', ->

        it 'should delete and reopen the database and return a promise', ->
            spyOn(indexedDBService, 'open').and.callThrough()
            db = indexedDBService.db
            indexedDBService.db = dbMock
            callback = jasmine.createSpy('cb')
            expect(indexedDBService.open).not.toHaveBeenCalled()
            indexedDBService.clear().then(callback)
            expect(callback).not.toHaveBeenCalled()
            $rootScope.$apply()
            expect(indexedDBService.open).toHaveBeenCalled()
            expect(callback).toHaveBeenCalled()
            indexedDBService.db = db

    describe 'filter(array, filters)', ->

        it 'should filter the array (one filter)', ->
            result = indexedDBService.filter(testArray, complete: false)
            expect(result.length).toBe(1)
            expect(result).toContain(testArray[0])

        it 'should filter the array (more than one filters)', ->
            result = indexedDBService.filter(testArray, complete: true, buildrequestid: 1)
            expect(result.length).toBe(2)
            expect(result).toContain(testArray[1])
            expect(result).toContain(testArray[2])

        it 'should filter the array (eq - equal)', ->
            result = indexedDBService.filter(testArray, 'complete__eq': true)
            expect(result.length).toBe(2)
            expect(result).toContain(testArray[1])
            expect(result).toContain(testArray[2])

        it 'should filter the array (ne - not equal)', ->
            result = indexedDBService.filter(testArray, 'complete__ne': true)
            expect(result.length).toBe(1)
            expect(result).toContain(testArray[0])

        it 'should filter the array (lt - less than)', ->
            result = indexedDBService.filter(testArray, 'buildid__lt': 3)
            expect(result.length).toBe(2)
            expect(result).toContain(testArray[1])
            expect(result).toContain(testArray[2])

        it 'should filter the array (le - less than or equal to)', ->
            result = indexedDBService.filter(testArray, 'buildid__le': 3)
            expect(result.length).toBe(3)

        it 'should filter the array (gt - greater than)', ->
            result = indexedDBService.filter(testArray, 'started_at__gt': 1417803025)
            expect(result.length).toBe(1)
            expect(result).toContain(testArray[1])

        it 'should filter the array (ge - greater than or equal to)', ->
            result = indexedDBService.filter(testArray, 'started_at__ge': 1417803025)
            expect(result.length).toBe(2)
            expect(result).toContain(testArray[1])
            expect(result).toContain(testArray[2])

        it 'should convert on/off, true/false, yes/no to boolean', ->
            resultTrue = indexedDBService.filter(testArray, complete: true)
            resultFalse = indexedDBService.filter(testArray, complete: false)

            result = indexedDBService.filter(testArray, complete: 'on')
            expect(result).toEqual(resultTrue)
            result = indexedDBService.filter(testArray, complete: 'true')
            expect(result).toEqual(resultTrue)
            result = indexedDBService.filter(testArray, complete: 'yes')
            expect(result).toEqual(resultTrue)

            result = indexedDBService.filter(testArray, complete: 'off')
            expect(result).toEqual(resultFalse)
            result = indexedDBService.filter(testArray, complete: 'false')
            expect(result).toEqual(resultFalse)
            result = indexedDBService.filter(testArray, complete: 'no')
            expect(result).toEqual(resultFalse)

    describe 'sort(array, order)', ->

        it 'should sort the array (one parameter)', ->
            result = indexedDBService.sort(testArray, 'buildid')
            expect(result[0]).toEqual(testArray[1])
            expect(result[1]).toEqual(testArray[2])
            expect(result[2]).toEqual(testArray[0])

        it 'should sort the array (one parameter, - reverse)', ->
            result = indexedDBService.sort(testArray, '-buildid')
            expect(result[0]).toEqual(testArray[0])
            expect(result[1]).toEqual(testArray[2])
            expect(result[2]).toEqual(testArray[1])

        it 'should sort the array (more parameter)', ->
            result = indexedDBService.sort(testArray, ['builderid', '-buildid'])
            expect(result[0]).toEqual(testArray[0])
            expect(result[1]).toEqual(testArray[2])
            expect(result[2]).toEqual(testArray[1])

    describe 'paginate(array, offset, limit)', ->

        it 'should slice the array (only offset)', ->
            result = indexedDBService.paginate(testArray, 1)
            expect(result.length).toBe(2)
            expect(result[0]).toEqual(testArray[1])
            expect(result[1]).toEqual(testArray[2])

        it 'should slice the array (only limit)', ->
            result = indexedDBService.paginate(testArray, null, 1)
            expect(result.length).toBe(1)
            expect(result[0]).toEqual(testArray[0])

        it 'should slice the array (offset, limit)', ->
            result = indexedDBService.paginate(testArray, 1, 1)
            expect(result.length).toBe(1)
            expect(result[0]).toEqual(testArray[1])

        it 'should return an empty array when the offset >= array.length', ->
            result = indexedDBService.paginate(testArray, 3)
            expect(result.length).toBe(0)
            result = indexedDBService.paginate(testArray, 4)
            expect(result.length).toBe(0)

        it 'should return the array when the limit >= array.length', ->
            result = indexedDBService.paginate(testArray, 2, 3)
            expect(result.length).toBe(1)
            expect(result[0]).toEqual(testArray[2])

    describe 'fields(array, fields)', ->

        it 'should return an array with elements having only certain fields (one field)', ->
            result = indexedDBService.fields(testArray, 'buildid')
            expect(result.length).toBe(testArray.length)
            for r in result
                expect(Object.keys(r)).toEqual(['buildid'])

        it 'should return an array with elements having only certain fields (more fields)', ->
            result = indexedDBService.fields(testArray, ['buildid', 'buildrequestid'])
            expect(result.length).toBe(testArray.length)
            for r in result
                expect(Object.keys(r)).toEqual(['buildid', 'buildrequestid'])

    describe 'processUrl(url)', ->

        it 'should return [root, query, id] (empty query + id)', ->
            indexedDBService.processUrl('typeA/11').then ([tableName, query, id]) ->
                expect(tableName).toBe('typeA')
                expect(query).toEqual({})
                expect(id).toBe(11)

            indexedDBService.processUrl('typeA/11/typeB/stringB').then ([tableName, query, id]) ->
                expect(tableName).toBe('typeB')
                expect(query).toEqual({})
                # the id of typeB is a string
                expect(id).toBe('stringB')

            indexedDBService.processUrl('typeB/11/typeC/12').then ([tableName, query, id]) ->
                expect(tableName).toBe('typeC')
                expect(query).toEqual({})
                expect(id).toBe(12)

            $rootScope.$apply()

        it 'should return [root, query, id] (empty query + no id)', ->
            indexedDBService.processUrl('typeC').then ([tableName, query, id]) ->
                expect(tableName).toBe('typeC')
                expect(query).toEqual({})
                expect(id).toBeNull()

            $rootScope.$apply()

        it 'should return [root, query, id] (query including number or string field)', ->
            indexedDBService.processUrl('typeA/11/typeB/stringID/typeC/1').then ([tableName, query, id]) ->
                expect(tableName).toBe('typeC')
                expect(query).toEqual({idB: 'stringID', numberC: 1})
                expect(id).toBeNull()

            indexedDBService.processUrl('typeB/11/typeC/stringID').then ([tableName, query, id]) ->
                expect(tableName).toBe('typeC')
                expect(query).toEqual({idB: 11, stringC: 'stringID'})
                expect(id).toBeNull()

            indexedDBService.processUrl('typeC/stringID').then ([tableName, query, id]) ->
                expect(tableName).toBe('typeC')
                expect(query).toEqual({stringC: 'stringID'})
                expect(id).toBeNull()

            indexedDBService.processUrl('typeB/stringID/typeC').then ([tableName, query, id]) ->
                expect(tableName).toBe('typeC')
                expect(query).toEqual({idB: 'stringID'})
                expect(id).toBeNull()

            $rootScope.$apply()

        it 'should trow and error if there is no match for a certain url', ->
            fn = -> indexedDBService.processUrl('typeA/11/typeB/12')
            expect(fn).toThrowError()

    describe 'processSpecification(specification)', ->

        it 'should return the indexedDB stores', ->
            specification =
                test1:
                    id: 'id1'
                    fields: [
                        'id1'
                        'field1'
                        'field2'
                    ]
                test2:
                    id: null
                    fields: [
                        'fieldA'
                        'fieldB'
                    ]

            result = indexedDBService.processSpecification(specification)
            expect(result.test1).toBe('&id1,field1,field2')
            expect(result.test2).toBe('++id,fieldA,fieldB')
