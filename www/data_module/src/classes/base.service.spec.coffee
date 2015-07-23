describe 'Base class', ->
    beforeEach module 'bbData'

    Base = dataService = socketService = $q = null
    injected = ($injector) ->
        Base = $injector.get('Base')
        dataService = $injector.get('dataService')
        socketService = $injector.get('socketService')
        $q = $injector.get('$q')

    beforeEach(inject(injected))

    it 'should be defined', ->
        expect(Base).toBeDefined()

    it 'should merge the passed in object with the instance', ->
        object = a: 1, b: 2
        base = new Base(object, 'ab')
        expect(base.a).toEqual(object.a)
        expect(base.b).toEqual(object.b)

    it 'should have loadXxx function for child endpoints', ->
        children = ['a', 'bcd', 'ccc']
        base = new Base({}, 'ab', children)
        for e in children
            E = e[0].toUpperCase() + e[1..-1].toLowerCase()
            expect(angular.isFunction(base["load#{E}"])).toBeTruthy()

    it 'should subscribe a listener to socket service events', ->
        expect(socketService.eventStream.listeners.length).toBe(0)
        base = new Base({}, 'ab')
        expect(socketService.eventStream.listeners.length).toBe(1)

    it 'should remove the listener on unsubscribe', ->
        expect(socketService.eventStream.listeners.length).toBe(0)
        base = new Base({}, 'ab')
        expect(socketService.eventStream.listeners.length).toBe(1)
        base.unsubscribe()
        expect(socketService.eventStream.listeners.length).toBe(0)

    it 'should update the instance when the event key matches', ->
        object = buildid: 1, a: 2, b: 3
        base = new Base(object, 'builds')
        expect(base.a).toEqual(object.a)
        socketService.eventStream.push
            k: 'builds/2/update'
            m: a: 3
        expect(base.a).toEqual(object.a)
        socketService.eventStream.push
            k: 'builds/1/update'
            m:
                a: 3
                c: 4
        expect(base.a).toEqual(3)
        expect(base.c).toEqual(4)

    it 'should remove the listeners of child endpoints on unsubscribe', ->
        base = new Base({}, '', ['ccc'])
        child = new Base({}, '')
        response = [child]
        p = $q.resolve(response)
        p.getArray = -> return response
        spyOn(dataService, 'get').and.returnValue(p)
        base.loadCcc()
        expect(base.ccc).toEqual(response)
        expect(socketService.eventStream.listeners.length).toBe(2)
        base.unsubscribe()
        expect(socketService.eventStream.listeners.length).toBe(0)
