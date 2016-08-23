describe 'force', () ->
    it 'should create a build', () ->
        browser.get('#/builders/1')
        lastbuild = element.all(By.css('span.badge-status.results_SUCCESS')).count()
        browser.get('#/builders/1/force/force')
        browser.waitForAngular()
        element(By.buttonText('Start Build')).click()
        browser.get('#/builders/1')
        successBuildIncrease =  ->
            lastbuild.then (lastbuild)->
                element.all(By.css('span.badge-status.results_SUCCESS'))
                .count().then (nextbuild)->
                    return +nextbuild == +lastbuild + 1
        browser.wait(successBuildIncrease, 20000)
        browser.get('#/waterfall')
        expect(element.all(By.css('rect.success')).count()).toBeGreaterThan(0)
