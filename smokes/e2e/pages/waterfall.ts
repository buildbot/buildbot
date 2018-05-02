// this file will contains the different generic functions which
// will be called by the different tests

import {browser, by, element, ExpectedConditions as EC} from 'protractor';
import { BasePage } from "./base";

export class WaterfallPage extends BasePage {
    constructor(builder) {
        {
          super();
          let thisFn = (() => { return this; }).toString();
          let thisName = thisFn.slice(thisFn.indexOf('return') + 6 + 1, thisFn.indexOf(';')).trim();
        }
        this.builder = builder;
    }

    async go() {
        await browser.get('#/waterfall');
        await browser.wait(EC.urlContains('#/waterfall'),
                           5000,
                           "URL does not contain #/waterfall");
    }

    async checkBuilder() {
        const currentUrl = await browser.getCurrentUrl();
        expect(currentUrl).toContain("builders/");
    }

    async checkBuildResult() {
        const firstLinkInPopup = element.all(By.css('.modal-dialog a')).first();
        await firstLinkInPopup.click();
        const currentUrl = await browser.getCurrentUrl();
        expect(currentUrl).toContain("builders/");
        expect(currentUrl).toContain("builds/");
    }

    async goBuild() {
        const buildList = element.all(By.css('text.id')).last();
        await buildList.click();
    }

    async goBuildAndClose() {
        await this.goBuild();
        const popupClose = element.all(By.css('i.fa-times'));
        await popupClose.click();
        const dialogIsPresent = await $('modal-dialog').isPresent();
        expect(dialogIsPresent).toBeFalsy();
    }

    async goBuildAndCheck() {
        const self = this;
        await self.goBuild();
        await self.checkBuildResult();
    }

    async goBuilderAndCheck(builderRef) {
        const self = this;
        const localBuilder = element.all(By.linkText(this.builder));
        await this.clickWhenClickable(localBuilder);
        await self.checkBuilder();
    }
}
