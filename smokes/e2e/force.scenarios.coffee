# coffee script
# test goal: checks the capability to define a reason and to cancel/start the build

forcePage = require('./force.coffee')
builderPage = require('./builder.coffee')

describe('', () ->
    force = null
    builder = null

    beforeEach(() ->
        builder = new builderPage('runtest', 'force')
        force =  new forcePage()
        builder.goDefault()
    )

    lastbuild = null
    describe 'force', () ->
        it 'should create a build', () ->

            lastbuild = 0
            builder.go()
            builder.getLastSuccessBuildNumber().then (lastbuild) ->
                builder.goForce()
                force.getStartButton().click()
                builder.go()
                builder.waitNextBuildFinished(lastbuild)
)
