describe 'Collection', ->
    beforeEach module 'bbData'
    beforeEach module ($provide) ->
        $provide.constant 'SPECIFICATION', asd: id: 'asdid'

    Collection = $q = $rootScope = tabexService = indexedDBService = c = undefined
    injected = ($injector) ->
        $q = $injector.get('$q')
        $rootScope = $injector.get('$rootScope')
        Collection = $injector.get('Collection')
        tabexService = $injector.get('tabexService')
        indexedDBService = $injector.get('indexedDBService')

        c = new Collection('asd')

    beforeEach(inject(injected))

    it 'should be defined', ->
        expect(Collection).toBeDefined()
        expect(c).toBeDefined()

    describe 'subscribe()', ->

        it 'should subscribe on tabex events', ->
            spyOn(tabexService, 'on').and.returnValue(null)
            spyOn(indexedDBService, 'get').and.returnValue($q.resolve([]))
            expect(tabexService.on).not.toHaveBeenCalled()
            ready = jasmine.createSpy('ready')

            c.subscribe().then(ready)
            expect(tabexService.on).toHaveBeenCalledWith('asd/*/*', {}, c.listener)
            c.listener(tabexService.EVENTS.READY)
            expect(ready).not.toHaveBeenCalled()
            $rootScope.$apply()
            expect(ready).toHaveBeenCalled()

    describe 'unsubscribe()', ->

        it 'should unsubscribe from tabex events', ->
            spyOn(tabexService, 'off').and.returnValue(null)
            expect(tabexService.off).not.toHaveBeenCalled()
            c.unsubscribe()
            expect(tabexService.off).toHaveBeenCalledWith('asd/*/*', {}, c.listener)

        it 'should call unsubscribe on every child that has an unsubscribe function', ->
            obj = unsubscribe: jasmine.createSpy('unsubscribe')
            c.push(obj)
            expect(obj.unsubscribe).not.toHaveBeenCalled()
            c.unsubscribe()
            expect(obj.unsubscribe).toHaveBeenCalled()

    describe 'listener(event)', ->

        it 'should read the data from indexedDB', ->
            spyOn(indexedDBService, 'get').and.returnValue($q.resolve())
            expect(indexedDBService.get).not.toHaveBeenCalled()
            c.listener(tabexService.EVENTS.READY)
            expect(indexedDBService.get).toHaveBeenCalledWith('asd', {})

        it 'should call the ready handler on ready event', ->
            data = [{data: 1}]
            spyOn(indexedDBService, 'get').and.returnValue($q.resolve(data))
            spyOn(c, 'readyHandler')
            c.listener(tabexService.EVENTS.READY)
            expect(c.readyHandler).not.toHaveBeenCalled()
            $rootScope.$apply()
            expect(c.readyHandler).toHaveBeenCalledWith(data)

        it 'should not call the ready handler when it is already filled with data', ->
            data = [{data: 1}]
            spyOn(indexedDBService, 'get').and.returnValue($q.resolve(data))
            spyOn(c, 'readyHandler')
            expect(c.readyHandler).not.toHaveBeenCalled()
            c.listener(tabexService.EVENTS.READY)
            $rootScope.$apply()
            c.listener(tabexService.EVENTS.READY)
            expect(c.readyHandler.calls.count()).toBe(1)

        it 'should call the update handler on update event', ->
            data = [{data: 1}]
            spyOn(indexedDBService, 'get').and.returnValue($q.resolve(data))
            spyOn(c, 'updateHandler')
            c.listener(tabexService.EVENTS.UPDATE)
            expect(c.updateHandler).not.toHaveBeenCalled()
            $rootScope.$apply()
            expect(c.updateHandler).toHaveBeenCalledWith(data)

        it 'should call the new handler on new event', ->
            data = [{data: 1}]
            spyOn(indexedDBService, 'get').and.returnValue($q.resolve(data))
            spyOn(c, 'newHandler')
            c.listener(tabexService.EVENTS.NEW)
            expect(c.newHandler).not.toHaveBeenCalled()
            $rootScope.$apply()
            expect(c.newHandler).toHaveBeenCalledWith(data)

        it 'should remove the subscribe field from the query', ->
            query = subscribe: false
            c = new Collection('asd', query)
            spyOn(indexedDBService, 'get').and.returnValue($q.resolve())
            c.listener(tabexService.EVENTS.READY)
            expect(indexedDBService.get).toHaveBeenCalledWith('asd', {})
            expect(c.getQuery()).toEqual(query)

    describe 'readyHandler(data)', ->

        it 'should fill up the collection', ->
            data = [{data: 1}, {data: 2}]
            spyOn(indexedDBService, 'get').and.returnValue($q.resolve(data))
            c.listener(tabexService.EVENTS.READY)
            expect(c.length).not.toBe(data.length)
            $rootScope.$apply()
            expect(c.length).toBe(data.length)

    describe 'updateHandler(data)', ->

        it 'should update the data where the id matches', ->
            data = [
                id: 1
                data: 'a'
            ,
                id: 2
                data: 'b'
            ]
            spyOn(indexedDBService, 'get').and.callFake -> $q.resolve(data)
            c.listener(tabexService.EVENTS.READY)
            $rootScope.$apply()
            c.forEach (e) -> data.forEach (i) ->
                if e.id is i.id then expect(e.data).toEqual(i.data)

            data =
                id: 1
                data: 'c'
            c.listener(tabexService.EVENTS.UPDATE)
            $rootScope.$apply()
            c.forEach (e) ->
                if e.id is data.id then expect(e.data).toEqual(data.data)
