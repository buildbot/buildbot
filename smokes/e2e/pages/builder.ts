// this file will contains the different generic functions which
// will be called by the different tests

import {browser, by, element, ExpectedConditions as EC} from 'protractor';
import { BasePage } from "./base";

export class BuilderPage extends BasePage {
    constructor(builder, forcename) {
        {
          super();
          let thisFn = (() => { return this; }).toString();
          let thisName = thisFn.slice(thisFn.indexOf('return') + 6 + 1, thisFn.indexOf(';')).trim();
        }
        this.builder = builder;
        this.forceName=forcename;
    }

    async goDefault() {
        await browser.get('#/builders');
    }

    async go() {
        await browser.get('#/builders');
        await browser.wait(EC.urlContains('#/builders'),
                           5000,
                           "URL does not contain #/builders");
        const localBuilder = element.all(By.linkText(this.builder));
        await localBuilder.click();
    }

    async goForce() {
        await this.go();
        await element.all(By.buttonText(this.forceName)).first().click();
    }

    async goBuild(buildRef) {
        await this.go();
        await element.all(By.linkText(buildRef.toString())).click();
    }

    async getLastSuccessBuildNumber() {
        let elements = await element.all(By.css('span.badge-status.results_SUCCESS'));
        if (elements.length === 0) {
            return 0;
        }
        let numberstr = await elements[0].getText();
        return +numberstr;
    }

    async waitNextBuildFinished(reference) {
        const self = this;
        const buildCountIncrement = () =>
            self.getLastSuccessBuildNumber().then(currentBuildCount => currentBuildCount === (reference + 1))
        ;
        await browser.wait(buildCountIncrement, 20000);
    }

    async waitGoToBuild(expected_buildnumber) {
        const isInBuild = async () =>
            {
                let buildUrl = await browser.getCurrentUrl();
                const split = buildUrl.split("/");
                const builds_part = split[split.length-2];
                const number = +split[split.length-1];
                if (builds_part !== "builds") {
                    return false;
                }
                if (number !== expected_buildnumber) {
                    return false;
                }
                return true;
            }
        await browser.wait(isInBuild, 20000);
    }

    getStopButton() {
        return element(By.buttonText('Stop'));
    }

    getPreviousButton() {
        return element(By.partialLinkText('Previous'));
    }

    getNextButton() {
        return element(By.partialLinkText('Next'));
    }

    getRebuildButton() {
        return element(By.buttonText('Rebuild'));
    }

    async checkBuilderURL() {
        const builderLink = element.all(By.linkText(this.builder));
        expect(await builderLink.count()).toBeGreaterThan(0);
    }
}
