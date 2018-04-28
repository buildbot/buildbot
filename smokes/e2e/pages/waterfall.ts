// this file will contains the different generic functions which
// will be called by the different tests

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

    go() {
        return browser.get('#/waterfall');
    }

    checkBuilder() {
        return browser.getCurrentUrl().then(currentUrl => expect(currentUrl).toContain("builders/"));
    }

    checkBuildResult() {
        const firstLinkInPopup = element.all(By.css('.modal-dialog a')).first();
        firstLinkInPopup.click();
        return browser.getCurrentUrl().then(function(currentUrl) {
            expect(currentUrl).toContain("builders/");
            expect(currentUrl).toContain("builds/");
        });
    }

    goBuild() {
        const buildList = element.all(By.css('text.id')).last();
        return buildList.click();
    }

    goBuildAndClose() {
        const self =  this;
        self.goBuild();
        const popupClose = element.all(By.css('i.fa-times'));
        popupClose.click();
        expect($('modal-dialog').isPresent()).toBeFalsy();
    }

    goBuildAndCheck() {
        const self =  this;
        self.goBuild();
        return self.checkBuildResult();
    }

    goBuilderAndCheck(builderRef) {
        const self = this;
        const localBuilder = element.all(By.linkText(this.builder));
        this.clickWhenClickable(localBuilder);
        return self.checkBuilder();
    }
}
