// this file will contains the different generic functions which
// will be called by the different tests

const BasePage = require("./base.js");

class SettingsPage extends BasePage {
    constructor(builder) {
        {
          super();
          let thisFn = (() => { return this; }).toString();
          let thisName = thisFn.slice(thisFn.indexOf('return') + 6 + 1, thisFn.indexOf(';')).trim();
        }
        this.builder = builder;
    }


    goSettings() {
        return browser.get('#/settings');
    }
    getItem(group, name) {
        return  element(By.css(`form[name='${group}'] [name='${name}']`));
    }
    changeScallingFactor(scallingVar) {
        const scallingFactorForm = this.getItem("Waterfall", "scaling_waterfall");
        return scallingFactorForm.clear().then(() => scallingFactorForm.sendKeys(scallingVar));
    }

    checkScallingFactor(scallingVar) {
        const scallingFactor = this.getItem("Waterfall", "scaling_waterfall");
        expect(scallingFactor.getAttribute('value')).toEqual(scallingVar);
    }

    changeColumnWidth(columnVar) {
        const columnWidthForm = this.getItem("Waterfall", "min_column_width_waterfall");
        return columnWidthForm.clear().then(() => columnWidthForm.sendKeys(columnVar));
    }

    checkColumnWidth(columnVar) {
        const columnWidthForm = this.getItem("Waterfall", "min_column_width_waterfall");
        expect(columnWidthForm.getAttribute('value')).toEqual(columnVar);
    }

    changeLazyLoadingLimit(lazyLoadingLimit) {
        const lazyLoadingLimitForm = this.getItem("Waterfall", "lazy_limit_waterfall");
        return lazyLoadingLimitForm.clear().then(() => lazyLoadingLimitForm.sendKeys(lazyLoadingLimit));
    }

    checkLazyLoadingLimit(lazyLoadingLimit) {
        const lazyLoadingLimitForm = this.getItem("Waterfall", "lazy_limit_waterfall");
        expect(lazyLoadingLimitForm.getAttribute('value')).toEqual(lazyLoadingLimit);
    }

    changeIdleTime(idleTimeVar) {
        const idleTimeForm = this.getItem("Waterfall", "idle_threshold_waterfall");
        return idleTimeForm.clear().then(() => idleTimeForm.sendKeys(idleTimeVar));
    }

    checkIdleTime(idleTimeVar) {
        const idleTimeForm = this.getItem("Waterfall", "idle_threshold_waterfall");
        expect(idleTimeForm.getAttribute('value')).toEqual(idleTimeVar);
    }

    changeMaxBuild(maxBuildVar) {
        const maxBuildForm = this.getItem("Console", "buildLimit");
        return maxBuildForm.clear().then(() => maxBuildForm.sendKeys(maxBuildVar));
    }

    checkMaxBuild(maxBuildVar) {
        const maxBuildForm = this.getItem("Console", "buildLimit");
        expect(maxBuildForm.getAttribute('value')).toEqual(maxBuildVar);
    }

    changeMaxRecentsBuilders(maxBuildersVar) {
        const maxBuilderForm = this.getItem("Console", "changeLimit");
        return maxBuilderForm.clear().then(() => maxBuilderForm.sendKeys(maxBuildersVar));
    }

    checkMaxRecentsBuilders(maxBuildersVar) {
        const maxBuilderForm = this.getItem("Console", "changeLimit");
        expect(maxBuilderForm.getAttribute('value')).toEqual(maxBuildersVar);
    }

    changeShowWorkerBuilders(showWorkerBuildersVar) {
        const showWorkerBuildersForm = this.getItem("Workers", "showWorkerBuilders");
        return showWorkerBuildersForm.isSelected().then(function(checked) {
            if (checked !== showWorkerBuildersVar) { return showWorkerBuildersForm.click(); }
        });
    }

    checkShowWorkerBuilders(showWorkerBuildersVar) {
        const showWorkerBuildersForm = this.getItem("Workers", "showWorkerBuilders");
        expect(showWorkerBuildersForm.isSelected()).toEqual(showWorkerBuildersVar);
    }
}

module.exports = SettingsPage;
