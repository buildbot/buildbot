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
