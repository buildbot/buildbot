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


    describe 'previousnextlink', () ->
        it 'should navigate in the builds history by using the previous next links', () ->
            builder.go()
            builder.getLastSuccessBuildNumber().then (lastbuild) ->
                # Build #1
                builder.go()
                builder.goForce()
                force.getStartButton().click()
                builder.go()
                builder.waitNextBuildFinished(lastbuild)
                # Build #2
                builder.goForce()
                force.getStartButton().click()
                builder.go()
                builder.waitNextBuildFinished(+lastbuild + 1)
                builder.go()
                builder.goBuild(lastbuild)
                lastBuildURL = browser.getLocationAbsUrl()
                builder.getPreviousButton().click()
                expect(browser.getLocationAbsUrl()).not.toMatch(lastBuildURL)
                builder.getNextButton().click()
                expect(browser.getLocationAbsUrl()).toMatch(lastBuildURL)
)

describe('', () ->
    force = null
    builder = null

    beforeEach(() ->
        builder = new builderPage('slowruntest', 'force')
        force =  new forcePage()
        builder.goDefault()
    )

  describe 'forceandstop', () ->
      it 'should create a build with a dedicated reason and stop it during execution', () ->

          builder.go()
          builder.goForce()
          force.getStartButton().click()
          expect(browser.getLocationAbsUrl()).toMatch("/builders/\[1-9]/builds/\[1-9]")
          builder.getStopButton().click()
)
