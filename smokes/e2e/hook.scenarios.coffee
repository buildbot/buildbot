consolePage = require('./pages/console.coffee')
builderPage = require('./pages/builder.coffee')
homePage = require('./pages/home.coffee')

describe 'change hook', () ->
    builder = null
    console = null
    home = null

    beforeEach () ->
        builder = new builderPage('runtests0')
        console = new consolePage()
        home = new homePage()
        home.loginUser("homer@email.com", "doh!")

    afterEach () ->
        home.logOut()

    it 'should create a build', () ->
        builder.go()
        builder.getLastSuccessBuildNumber().then (lastbuild) ->
            browser.executeAsyncScript (done)->
                $.post('change_hook/base', {
                    comments:'sd',
                    project:'pyflakes'
                    repository:'git://github.com/buildbot/pyflakes.git'
                    author:'foo <foo@bar.com>'
                    revision: 'HEAD'
                    branch:'master'
                    }, done)
            builder.waitNextBuildFinished(lastbuild)
        console.go()
        expect(console.countSuccess()).toBeGreaterThan(0)
