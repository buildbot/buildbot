beforeEach ->
    module 'waterfall_view'

describe 'Data service', ->

    dataService = builds = builders = null

    injected = ($injector) ->
        $rootScope = $injector.get('$rootScope')
        dataService = $injector.get('dataService')
        buildbotServiceMock = $injector.get('buildbotService')

        # Use mocked buildbotService to get the sample data
        buildbotServiceMock.all('builds').getList().then (b) ->
            builds = b
        buildbotServiceMock.all('builders').getList().then (b) ->
            builders = b
        $rootScope.$digest()

    beforeEach(inject(injected))

    it 'should be defined', ->
        expect(dataService).toBeDefined()
        # getGroups is a function
        expect(dataService.getGroups).toBeDefined()
        expect(typeof dataService.getGroups).toBe('function')
        # addStatus is a function
        expect(dataService.addStatus).toBeDefined()
        expect(typeof dataService.addStatus).toBe('function')

    it 'should add builds to builders', ->
        # Add builds to builders
        dataService.getGroups(builders, builds, 0)
        for build in builds
            # A builder should contain its build
            expect(builders[build.builderid - 1].builds).toContain(build)
        # Builders builds length should be equal to all builds length
        buildsInBuilders = 0
        for builder in builders
            buildsInBuilders += builder.builds.length
        expect(buildsInBuilders).toEqual(builds.length)

    it 'should create groups', ->
        # Create groups with a bigger threshold
        threshold = builds[1].started_at - builds[0].complete_at
        groups = dataService.getGroups(builders, builds, threshold)
        expect(groups.length).toBe(1)

        # Create groups with a smaller threshold
        threshold = builds[1].started_at - builds[0].complete_at
        groups = dataService.getGroups(builders, builds, threshold - 1)
        expect(groups.length).toBe(2)

        # Add builds to groups, all build have to be in one group
        buildsInGroups = 0
        for build in builds
            for group in groups
                group.builds ?= []
                if build.started_at <= group.min and build.complete_at <= group.max
                    group.builds.push(build)
                    buildsInGroups++
        expect(buildsInGroups).toEqual(builds.length)

        # If the time between two builds is less than the threshold, they should be in different groups
        for build1, i in builds
            for build2 in builds[i+1..]
                # If build2 starts earlier than build1, swap them
                if build2.buildid < build1.buildid
                    [build1, build2] = [build2, build1]
                if build2.started_at - build1.complete_at > threshold
                    expect(build1.groupid).not.toBe(build2.groupid)

    it 'should add complete_at to unfinished builds', ->
        unfinishedBuilds = builds.filter (build) -> not build.complete
        dataService.getGroups(builders, unfinishedBuilds, 0)
        for build in unfinishedBuilds
            expect(build.complete_at).toBeDefined()
            # It should be a correct timestamp
            expect(build.complete_at.toString().length).toBe(10)

    it 'should add status to builders', ->
        # Add builds to builders first
        dataService.getGroups(builders, builds, 0)
        dataService.addStatus(builders)
        for builder in builders
            if builder.complete then expect(builder.results).toBeDefined()
            else expect(builder.results).not.toBeDefined()