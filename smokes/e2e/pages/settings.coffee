# this file will contains the different generic functions which
# will be called by the different tests
# inspired by this methodology
# http://www.lindstromhenrik.com/using-protractor-with-coffeescript/
BasePage = require("./base.coffee")

class SettingsPage extends BasePage
    constructor: (builder) ->
        @builder = builder


    goSettings: () ->
        browser.get('#/settings')
    getItem: (group, name) ->
        return  element(By.css("form[name='#{group}'] [name='#{name}']"))
    changeScallingFactor: (scallingVar) ->
        scallingFactorForm = @getItem("Waterfall", "scaling_waterfall")
        scallingFactorForm.clear().then () ->
            scallingFactorForm.sendKeys(scallingVar)

    checkScallingFactor: (scallingVar) ->
        scallingFactor = @getItem("Waterfall", "scaling_waterfall")
        expect(scallingFactor.getAttribute('value')).toEqual(scallingVar)

    changeColumnWidth: (columnVar) ->
        columnWidthForm = @getItem("Waterfall", "min_column_width_waterfall")
        columnWidthForm.clear().then () ->
            columnWidthForm.sendKeys(columnVar)

    checkColumnWidth: (columnVar) ->
        columnWidthForm = @getItem("Waterfall", "min_column_width_waterfall")
        expect(columnWidthForm.getAttribute('value')).toEqual(columnVar)

    changeLazyLoadingLimit: (lazyLoadingLimit) ->
        lazyLoadingLimitForm = @getItem("Waterfall", "lazy_limit_waterfall")
        lazyLoadingLimitForm.clear().then () ->
            lazyLoadingLimitForm.sendKeys(lazyLoadingLimit)

    checkLazyLoadingLimit: (lazyLoadingLimit) ->
        lazyLoadingLimitForm = @getItem("Waterfall", "lazy_limit_waterfall")
        expect(lazyLoadingLimitForm.getAttribute('value')).toEqual(lazyLoadingLimit)

    changeIdleTime: (idleTimeVar) ->
        idleTimeForm = @getItem("Waterfall", "idle_threshold_waterfall")
        idleTimeForm.clear().then () ->
            idleTimeForm.sendKeys(idleTimeVar)

    checkIdleTime: (idleTimeVar) ->
        idleTimeForm = @getItem("Waterfall", "idle_threshold_waterfall")
        expect(idleTimeForm.getAttribute('value')).toEqual(idleTimeVar)

    changeMaxBuild: (maxBuildVar) ->
        maxBuildForm = @getItem("Console", "buildLimit")
        maxBuildForm.clear().then () ->
            maxBuildForm.sendKeys(maxBuildVar)

    checkMaxBuild: (maxBuildVar) ->
        maxBuildForm = @getItem("Console", "buildLimit")
        expect(maxBuildForm.getAttribute('value')).toEqual(maxBuildVar)

    changeMaxRecentsBuilders: (maxBuildersVar) ->
        maxBuilderForm = @getItem("Console", "changeLimit")
        maxBuilderForm.clear().then () ->
            maxBuilderForm.sendKeys(maxBuildersVar)

    checkMaxRecentsBuilders: (maxBuildersVar) ->
        maxBuilderForm = @getItem("Console", "changeLimit")
        expect(maxBuilderForm.getAttribute('value')).toEqual(maxBuildersVar)

    changeShowWorkerBuilders: (showWorkerBuildersVar) ->
        showWorkerBuildersForm = @getItem("Workers", "showWorkerBuilders")
        showWorkerBuildersForm.isSelected().then (checked) ->
            showWorkerBuildersForm.click() if checked != showWorkerBuildersVar

    checkShowWorkerBuilders: (showWorkerBuildersVar) ->
        showWorkerBuildersForm = @getItem("Workers", "showWorkerBuilders")
        expect(showWorkerBuildersForm.isSelected()).toEqual(showWorkerBuildersVar)

module.exports = SettingsPage
