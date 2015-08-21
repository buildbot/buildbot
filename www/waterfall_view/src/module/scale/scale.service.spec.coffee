describe 'Scale service', ->

    groups = [
                        # Y.M.D - h:m:s
        min: 1325376000 # 2012.01.01 - 0:0:0
        max: 1325548800 # 2012.01.03 - 0:0:0
    ,
        min: 1395104461 # 2014.03.18 - 1:1:1
        max: 1396450952 # 2014.04.02 - 15:2:32
    ]

    scaleService = scale = builders = null

    injected = ($injector) ->
        $rootScope = $injector.get('$rootScope')
        scaleService = $injector.get('scaleService')

        scale = new scaleService(window.d3)

        builders = [
            builderid: 1
            name: 'builder1'
        ,
            builderid: 2
            name: 'builder2'
        ,
            builderid: 3
            name: 'builder3'
        ,
            builderid: 4
            name: 'builder4'
        ]
        $rootScope.$digest()


    beforeEach(inject(injected))

    it 'should be defined', ->
        expect(scaleService).toBeDefined()
        expect(scale).toBeDefined()
        # getX is a function
        expect(scale.getX).toBeDefined()
        expect(typeof scale.getX).toBe('function')
        # getY is a function
        expect(scale.getY).toBeDefined()
        expect(typeof scale.getY).toBe('function')
        # getBuilderName is a function
        expect(scale.getBuilderName).toBeDefined()
        expect(typeof scale.getBuilderName).toBe('function')

    it 'should return a builderid to X scale', ->
        # Get new scale, range: 100
        idToX = scale.getX(builders, 100)
        # A build with smaller builderid should come first
        for builder, i in builders by 2
            a = idToX(builders[i].builderid)
            b = idToX(builders[i+1].builderid) or 100
            expect(a).toBeLessThan(b)
        # Out of domain
        expect(idToX(8)).toBeUndefined()

    it 'should return a build lenght to height scale', ->
        # gap: 5, range: 100
        idToY = scale.getY(groups, 5, 100)
        # Check gap size
        expect(idToY(groups[0].max) - idToY(groups[1].min)).toBe(5)
        # All dates are in domain
        dates = [
            1325376000 # 2012.01.01 - 0:0:0
            1325386000 # 2012.01.01 - 2:46:40
            1396328527 # 2014.04.01 - 5:2:7
        ]
        for date in dates
            # date -> coordinate -> date, the starting and the ending date should be equal
            expect(idToY.invert(idToY(date))).toEqual(date)
        # Later times have greater Y coordinate
        expect(idToY(date)).toBeGreaterThan(idToY(date + 10000))
        # Out of domain
        expect(idToY(1359731101)).toBeUndefined()
        expect(idToY.invert(120)).toBeUndefined()

    it 'should return a builderid to name scale', ->
        # Get new scale
        idToName = scale.getBuilderName(builders)
        # The return value should be the name of the builder
        for builder in builders
            expect(idToName(builder.builderid)).toEqual(builder.name)
