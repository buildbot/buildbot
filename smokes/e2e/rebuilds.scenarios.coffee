# coffee script
# test goal: checks the capability to navigate in a dedicated build
# to use previous and next link


forcePage = require('./force.coffee')
builderPage = require('./builder.coffee')

describe('', () ->
    force = null
    builder = null

    beforeEach(() ->
        builder = new builderPage('runtests', 'force')
        force =  new forcePage()
        builder.goDefault()
    )

    describe 'rebuild button', () ->
        it 'should navigate to a dedicated build and to use the rebuild button', () ->
            builder.go()
            builder.getLastSuccessBuildNumber().then (lastbuild) ->
                builder.goForce()
                force.getStartButton().click()
                builder.go()
                builder.waitNextBuildFinished(lastbuild)
                builder.goBuild(lastbuild)
                browser.getLocationAbsUrl().then (buildUrl) ->
                    builder.getRebuildButton().click()
                    builder.waitGoToBuild(lastbuild+2)

)
