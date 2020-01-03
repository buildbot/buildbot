// this file contains the different generic functions which
// will be called by the different tests

import { BasePage } from "./base";
import { browser, by, element, ExpectedConditions as EC, By } from 'protractor';

export class WaterfallPage extends BasePage {
    builder: string;

    constructor(builder: string) {
        super();
        this.builder = builder;
    }

    async go() {
        await browser.get('#/waterfall');
        await browser.wait(EC.urlContains('#/waterfall'),
                           10000,
                           "URL does not contain #/waterfall");
        await browser.wait(EC.elementToBeClickable($("div.waterfall")),
                           5000,
                           "waterfall is not clickable");
    }

    async checkBuilder() {
        const currentUrl = await browser.getCurrentUrl();
        expect(currentUrl).toContain("builders/");
    }

    async checkBuildResult() {
        const firstLinkInPopup = element.all(By.css('.modal-dialog a')).first();
        await browser.wait(EC.elementToBeClickable(firstLinkInPopup),
                           5000,
                           "first link in popup not clickable");
        await firstLinkInPopup.click();
        const currentUrl = await browser.getCurrentUrl();
        expect(currentUrl).toContain("builders/");
        expect(currentUrl).toContain("builds/");
    }

    async goBuild() {
        const buildList = element.all(By.css('text.id')).last();
        await browser.wait(EC.elementToBeClickable(buildList),
                           5000,
                           "build list not clickable");
        await buildList.click();
    }

    async goBuildAndClose() {
        await this.goBuild();
        const popupClose = element.all(By.css('i.fa-times')).first();
        await browser.wait(EC.elementToBeClickable(popupClose),
                           5000,
                           "popup close not clickable");
        await popupClose.click();
        const dialogIsPresent = await $('modal-dialog').isPresent();
        expect(dialogIsPresent).toBeFalsy();
    }

    async goBuildAndCheck() {
        await this.goBuild();
        await this.checkBuildResult();
    }

    async goBuilderAndCheck(builderRef) {
        let localBuilder = element(By.linkText(this.builder));
        await browser.wait(EC.elementToBeClickable(localBuilder),
                           5000,
                           "local builder not clickable");
        await localBuilder.click();
        await this.checkBuilder();
    }

    async goTagAndCheckUrl() {
        const firstTag = element.all(By.binding('tag')).first();
        await browser.wait(EC.elementToBeClickable(firstTag),
                           5000,
                           "first tag close not clickable");
        await firstTag.click();
        expect(browser.getCurrentUrl()).toContain(firstTag.getText());
    }

    async goUrlAndCheckTag() {
        await browser.get('#/waterfall?tags=runt');
        const selectedTag = element(by.className('label-success'));
        expect(await selectedTag.getText()).toContain('runt');
    }
}
