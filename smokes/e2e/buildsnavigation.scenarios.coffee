# coffee script
# test goal: checks the capability to navigate in a dedicated build
# to use previous and next link


forcePage = require('./pages/force.coffee')
builderPage = require('./pages/builder.coffee')
homePage = require('./pages/home.coffee')

describe 'previousnextlink', () ->
    force = null
    builder = null

    beforeEach(() ->
        builder = new builderPage('runtests', 'force')
        force =  new forcePage()
    )
    afterEach () ->
        new homePage().waitAllBuildsFinished()

    it 'has afterEach working', () ->
        return

    it 'should navigate in the builds history by using the previous next links', () ->
        builder.go()
        builder.getLastSuccessBuildNumber().then (lastbuild) ->
            # Build #1
            builder.goForce()
            force.getStartButton().click()
            builder.go()
            builder.waitNextBuildFinished(lastbuild)
            # Build #2
            builder.goForce()
            force.getStartButton().click()
            builder.go()
            builder.waitNextBuildFinished(+lastbuild + 1)
            builder.goBuild(+lastbuild + 2)
            lastBuildURL = browser.getCurrentUrl()
            builder.clickWhenClickable(builder.getPreviousButton())
            expect(browser.getCurrentUrl()).not.toMatch(lastBuildURL)
            builder.clickWhenClickable(builder.getNextButton())
            expect(browser.getCurrentUrl()).toMatch(lastBuildURL)

describe 'forceandstop', () ->
    force = null
    builder = null

    beforeEach(() ->
        builder = new builderPage('slowruntests', 'force')
        force =  new forcePage()
    )

    it 'should create a build with a dedicated reason and stop it during execution', () ->

        builder.goForce()
        force.getStartButton().click()
        expect(browser.getCurrentUrl()).toMatch("/builders/\[1-9]/builds/\[1-9]")
        builder.getStopButton().click()
