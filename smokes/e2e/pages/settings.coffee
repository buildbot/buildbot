# this file will contains the different generic functions which
# will be called by the different tests
# inspired by this methodology
# http://www.lindstromhenrik.com/using-protractor-with-coffeescript/

class settingsPage
    constructor: (builder) ->
        @builder = builder


    goSettings: () ->
        browser.get('#/settings')

    changeScallingFactor: (scallingVar) ->
        scallingFactorForm = element.all(By.css('input.form-control')).first()
        scallingFactorForm.clear().then () ->
            scallingFactorForm.sendKeys(scallingVar)

    checkScallingFactor: (scallingVar) ->
        scallingFactor = element.all(By.css('input.form-control')).first()
        expect(scallingFactor.getAttribute('value')).toEqual(scallingVar)

    changeColumnWidth: (columnVar) ->
        columnWidthForm = element.all(By.css('input.form-control')).get(1)
        columnWidthForm.clear().then () ->
            columnWidthForm.sendKeys(columnVar)

    checkColumnWidth: (columnVar) ->
        columnWidthForm = element.all(By.css('input.form-control')).get(1)
        expect(columnWidthForm.getAttribute('value')).toEqual(columnVar)

    changeLazyLoadingLimit: (lazyLoadingLimit) ->
        lazyLoadingLimitForm = element.all(By.css('input.form-control')).get(2)
        lazyLoadingLimitForm.clear().then () ->
            lazyLoadingLimitForm.sendKeys(lazyLoadingLimit)

    checkLazyLoadingLimit: (lazyLoadingLimit) ->
        lazyLoadingLimitForm = element.all(By.css('input.form-control')).get(2)
        expect(lazyLoadingLimitForm.getAttribute('value')).toEqual(lazyLoadingLimit)

    changeIdleTime: (idleTimeVar) ->
        idleTimeForm = element.all(By.css('input.form-control')).get(3)
        idleTimeForm.clear().then () ->
            idleTimeForm.sendKeys(idleTimeVar)

    checkIdleTime: (idleTimeVar) ->
        idleTimeForm = element.all(By.css('input.form-control')).get(3)
        expect(idleTimeForm.getAttribute('value')).toEqual(idleTimeVar)

    changeMaxBuild: (maxBuildVar) ->
        maxBuildForm = element.all(By.css('input.form-control')).get(4)
        maxBuildForm.clear().then () ->
            maxBuildForm.sendKeys(maxBuildVar)

    checkMaxBuild: (maxBuildVar) ->
        maxBuildForm = element.all(By.css('input.form-control')).get(4)
        expect(maxBuildForm.getAttribute('value')).toEqual(maxBuildVar)

    changeMaxRecentsBuilders: (maxBuildersVar) ->
        maxBuilderForm = element.all(By.css('input.form-control')).get(5)
        maxBuilderForm.clear().then () ->
            maxBuilderForm.sendKeys(maxBuildersVar)

    checkMaxRecentsBuilders: (maxBuildersVar) ->
        maxBuilderForm = element.all(By.css('input.form-control')).get(5)
        expect(maxBuilderForm.getAttribute('value')).toEqual(maxBuildersVar)

module.exports = settingsPage
