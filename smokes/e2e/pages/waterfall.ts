// this file contains the different generic functions which
// will be called by the different tests

import { BasePage } from "./base";
import { browser, by, element, ExpectedConditions as EC, By } from 'protractor';
import { bbrowser } from '../utils';

export class WaterfallPage extends BasePage {
    builder: string;

    constructor(builder: string) {
        super();
        this.builder = builder;
    }

    async go() {
        await bbrowser.get('#/waterfall');
        await bbrowser.wait(EC.urlContains('#/waterfall'),
                            "URL does not contain #/waterfall");
        await bbrowser.wait(EC.elementToBeClickable($("div.waterfall")),
                            "waterfall is not clickable");
    }

    async checkBuilder() {
        const currentUrl = await browser.getCurrentUrl();
        expect(currentUrl).toContain("builders/");
    }

    async checkBuildResult() {
        const firstLinkInPopup = element.all(By.css('.modal-dialog a')).first();
        await bbrowser.wait(EC.elementToBeClickable(firstLinkInPopup),
                            "first link in popup not clickable");
        await firstLinkInPopup.click();
        const currentUrl = await browser.getCurrentUrl();
        expect(currentUrl).toContain("builders/");
        expect(currentUrl).toContain("builds/");
    }

    async goBuild() {
        const buildList = element.all(By.css('text.id')).last();
        await bbrowser.wait(EC.elementToBeClickable(buildList),
                            "build list not clickable");
        await buildList.click();
    }

    async goBuildAndClose() {
        await this.goBuild();
        const popupClose = element.all(By.css('i.fa-times')).first();
        await bbrowser.wait(EC.elementToBeClickable(popupClose),
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
        await bbrowser.wait(EC.elementToBeClickable(localBuilder),
                            "local builder not clickable");
        await localBuilder.click();
        await this.checkBuilder();
    }

    async goTagAndCheckUrl() {
        const firstTag = element.all(By.binding('tag')).first();
        await bbrowser.wait(EC.elementToBeClickable(firstTag),
                            "first tag close not clickable");
        await firstTag.click();
        expect(browser.getCurrentUrl()).toContain(firstTag.getText());
        await bbrowser.wait(EC.elementToBeClickable(firstTag),
                            "first tag close not clickable");

    }

    async goUrlAndCheckTag() {
        await bbrowser.get('#/waterfall?tags=runt');
        const selectedTag = element(by.className('label-success'));
        expect(await selectedTag.getText()).toContain('runt');
        const firstTag = element.all(By.binding('tag')).first();
        await bbrowser.wait(EC.elementToBeClickable(firstTag),
                            "first tag close not clickable");
    }
}
