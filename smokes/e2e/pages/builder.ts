// this file will contains the different generic functions which
// will be called by the different tests

import { BasePage } from "./base";
import { browser, by, element, ExpectedConditions as EC } from 'protractor';

export class BuilderPage extends BasePage {
    builder: string;
    forceName: string;
    constructor(builder, forcename) {
        super();
        this.builder = builder;
        this.forceName=forcename;
    }

    async goBuildersList() {
        await browser.get('#/builders');
        await browser.wait(EC.urlContains('#/builders'),
                           10000,
                           "URL does not contain #/builders");
    }

    async go() {
        await browser.get('#/builders');
        await browser.wait(EC.urlContains('#/builders'),
                           10000,
                           "URL does not contain #/builders");
        let localBuilder = element(By.linkText(this.builder));
        await browser.wait(EC.elementToBeClickable(localBuilder),
                           5000,
                           "local builder not clickable");
        await localBuilder.click();
    }

    async goForce() {
        await this.go();
        var forceButton = element.all(By.buttonText(this.forceName)).first();
        await browser.wait(EC.elementToBeClickable(forceButton),
                           5000,
                           "force button not clickable");
        await forceButton.click();
    }

    async goBuild(buildRef) {
        await this.go();
        var buildLink = element(By.linkText(buildRef.toString()));
        await browser.wait(EC.elementToBeClickable(buildLink),
                           5000,
                           "build link not clickable");
        await buildLink.click();
    }

    async getLastFinishedBuildNumber() {
        let finishedBuildCss = 'span.badge-status.results_SUCCESS, ' +
                               'span.badge-status.results_WARNINGS, ' +
                               'span.badge-status.results_FAILURE, ' +
                               'span.badge-status.results_SKIPPED, ' +
                               'span.badge-status.results_EXCEPTION, ' +
                               'span.badge-status.results_RETRY, ' +
                               'span.badge-status.results_CANCELLED ';
        let elements = await element.all(By.css(finishedBuildCss));
        if (elements.length === 0) {
            return 0;
        }
        let numberstr = await elements[0].getText();
        if (numberstr == "SUCCESS") {
            await browser.actions().mouseMove(element(by.css('.navbar-brand'))).perform();
            numberstr = await elements[0].getText();
        }
        return +numberstr;
    }

    async waitBuildFinished(reference) {
        const self = this;
        async function buildCountIncrement() {
            let currentBuildCount = await self.getLastFinishedBuildNumber();
            return currentBuildCount == reference;
        }
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
