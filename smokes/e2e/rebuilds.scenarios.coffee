# coffee script
# test goal: checks the capability to navigate in a dedicated build
# to use previous and next link


homePage = require('./pages/home.coffee')
forcePage = require('./pages/force.coffee')
builderPage = require('./pages/builder.coffee')

describe 'rebuilds', () ->
    force = null
    builder = null

    beforeEach () ->
        builder = new builderPage('runtests', 'force')
        force =  new forcePage()
        builder.goDefault()

    afterEach () ->
        new homePage().waitAllBuildsFinished()

    it 'should navigate to a dedicated build and to use the rebuild button', () ->
        builder.go()
        builder.getLastSuccessBuildNumber().then (lastbuild) ->
            builder.goForce()
            force.getStartButton().click()
            builder.go()
            builder.waitNextBuildFinished(lastbuild)
            builder.goBuild(lastbuild)
            browser.getCurrentUrl().then (buildUrl) ->
                builder.getRebuildButton().click()
                builder.waitGoToBuild(lastbuild+2)
