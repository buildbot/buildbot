consolePage = require('./pages/console.coffee')
builderPage = require('./pages/builder.coffee')
homePage = require('./pages/home.coffee')

describe 'change hook', () ->
    builder = null
    console = null
    beforeEach(() ->
        builder = new builderPage('runtests1', 'force')
        console = new consolePage()
    )
    afterEach () ->
        new homePage().waitAllBuildsFinished()

    it 'should create a build', () ->
        builder.go()
        builder.getLastSuccessBuildNumber().then (lastbuild) ->
            browser.executeAsyncScript (done)->
                $.post('change_hook/base', {
                    comments:'sd',
                    project:'pyflakes'
                    repository:'git://github.com/buildbot/pyflakes.git'
                    author:'foo'
                    branch:'master'
                    }, done)
            builder.waitNextBuildFinished(lastbuild)
        console.go()
        expect(console.countSuccess()).toBeGreaterThan(0)
