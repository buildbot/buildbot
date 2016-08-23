describe 'change hook', () ->
    it 'should create a build', () ->
        browser.get('#/builders/1')
        lastbuild = element.all(By.css('span.badge-status.results_SUCCESS')).count()
        browser.executeAsyncScript (done)->
            $.post('change_hook/base', {
                comments:'sd',
                project:'pyflakes'
                repository:'git://github.com/buildbot/pyflakes.git'
                author:'foo'
                branch:'master'
                }, done)
        browser.get('#/builders/1')
        successBuildIncrease =  ->
            lastbuild.then (lastbuild)->
                element.all(By.css('span.badge-status.results_SUCCESS'))
                .count().then (nextbuild)->
                    return +nextbuild == +lastbuild + 1
        browser.wait(successBuildIncrease, 20000)
        browser.get('#/console')
        expect(element.all(By.css('.badge-status.results_SUCCESS')).count()).toBeGreaterThan(0)
