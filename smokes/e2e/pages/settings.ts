// this file contains the different generic functions which
// will be called by the different tests

import { BasePage } from "./base";
import { browser, by, element, ExpectedConditions as EC } from 'protractor';

export class SettingsPage extends BasePage {
    builder: string;

    constructor(builder) {
        super();
        this.builder = builder;
    }

    async goSettings() {
        await browser.get('#/settings');
        await browser.wait(EC.urlContains('#/settings'),
                           10000,
                           "URL does not contain #/settings");
    }

    getItem(group, name) {
        return element(By.css(`form[name='${group}'] [name='${name}']`));
    }

    async changeScallingFactor(scallingVar) {
        const scallingFactorForm = this.getItem("Waterfall", "scaling_waterfall");
        await scallingFactorForm.clear();
        await scallingFactorForm.sendKeys(scallingVar);
    }

    async checkScallingFactor(scallingVar) {
        const scallingFactor = this.getItem("Waterfall", "scaling_waterfall");
        expect(await scallingFactor.getAttribute('value')).toEqual(scallingVar);
    }

    async changeColumnWidth(columnVar) {
        const columnWidthForm = this.getItem("Waterfall", "min_column_width_waterfall");
        await columnWidthForm.clear();
        await columnWidthForm.sendKeys(columnVar);
    }

    async checkColumnWidth(columnVar) {
        const columnWidthForm = this.getItem("Waterfall", "min_column_width_waterfall");
        expect(await columnWidthForm.getAttribute('value')).toEqual(columnVar);
    }

    async changeLazyLoadingLimit(lazyLoadingLimit) {
        const lazyLoadingLimitForm = this.getItem("Waterfall", "lazy_limit_waterfall");
        await lazyLoadingLimitForm.clear();
        await lazyLoadingLimitForm.sendKeys(lazyLoadingLimit);
    }

    async checkLazyLoadingLimit(lazyLoadingLimit) {
        const lazyLoadingLimitForm = this.getItem("Waterfall", "lazy_limit_waterfall");
        expect(await lazyLoadingLimitForm.getAttribute('value')).toEqual(lazyLoadingLimit);
    }

    async changeIdleTime(idleTimeVar) {
        const idleTimeForm = this.getItem("Waterfall", "idle_threshold_waterfall");
        await idleTimeForm.clear();
        await idleTimeForm.sendKeys(idleTimeVar);
    }

    async checkIdleTime(idleTimeVar) {
        const idleTimeForm = this.getItem("Waterfall", "idle_threshold_waterfall");
        expect(await idleTimeForm.getAttribute('value')).toEqual(idleTimeVar);
    }

    async changeMaxBuild(maxBuildVar) {
        const maxBuildForm = this.getItem("Console", "buildLimit");
        await maxBuildForm.clear()
        await maxBuildForm.sendKeys(maxBuildVar);
    }

    async checkMaxBuild(maxBuildVar) {
        const maxBuildForm = this.getItem("Console", "buildLimit");
        expect(await maxBuildForm.getAttribute('value')).toEqual(maxBuildVar);
    }

    async changeMaxRecentsBuilders(maxBuildersVar) {
        const maxBuilderForm = this.getItem("Console", "changeLimit");
        await maxBuilderForm.clear();
        await maxBuilderForm.sendKeys(maxBuildersVar);
    }

    async checkMaxRecentsBuilders(maxBuildersVar) {
        const maxBuilderForm = this.getItem("Console", "changeLimit");
        expect(await  maxBuilderForm.getAttribute('value')).toEqual(maxBuildersVar);
    }

    async changeShowWorkerBuilders(showWorkerBuildersVar) {
        const showWorkerBuildersForm = this.getItem("Workers", "showWorkerBuilders");
        const checked = await showWorkerBuildersForm.isSelected();
        if (checked !== showWorkerBuildersVar) {
            await showWorkerBuildersForm.click();
        }
    }

    async checkShowWorkerBuilders(showWorkerBuildersVar) {
        const showWorkerBuildersForm = this.getItem("Workers", "showWorkerBuilders");
        const isSelected = await showWorkerBuildersForm.isSelected();
        expect(isSelected).toEqual(showWorkerBuildersVar);
    }
}
