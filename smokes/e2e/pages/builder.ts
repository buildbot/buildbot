// this file will contains the different generic functions which
// will be called by the different tests

import { BasePage } from "./base";
import { ForcePage } from './force';
import { browser, by, element, ExpectedConditions as EC } from 'protractor';
import { bbrowser } from '../utils';

export class BuilderPage extends BasePage {
    builder: string;
    forceName: string;
    constructor(builder, forcename) {
        super();
        this.builder = builder;
        this.forceName=forcename;
    }

    async goBuildersList() {
        await bbrowser.get('#/builders');
        await bbrowser.wait(EC.urlContains('#/builders'),
                            "URL does not contain #/builders");
    }

    async go() {
        await bbrowser.get('#/builders');
        await bbrowser.wait(EC.urlContains('#/builders'),
                            "URL does not contain #/builders");
        let localBuilder = element(By.linkText(this.builder));
        await bbrowser.wait(EC.elementToBeClickable(localBuilder),
                            "local builder not clickable");
        await localBuilder.click();

        const isBuilderPage = async () =>
        {
            let url = await browser.getCurrentUrl();
            return (new RegExp("#/builders/[0-9]+$")).test(url);
        };
        await bbrowser.wait(isBuilderPage, "Did not got to builder page");
    }

    async goForce() {
        await this.go();
        var forceButton = element.all(By.buttonText(this.forceName)).first();
        await bbrowser.wait(EC.elementToBeClickable(forceButton),
                            "force button not clickable");
        await forceButton.click();
        return new ForcePage();
    }

    async goBuild(buildRef) {
        await this.go();

        const matchLink = async (elem) => {
            return await elem.getText() == buildRef.toString();
        };

        var buildLink = element.all(By.css('.bb-buildid-link'))
                               .filter(matchLink)
                               .first();
        await bbrowser.wait(EC.elementToBeClickable(buildLink),
                            "build link not clickable");
        await buildLink.click();
    }

    async getLastFinishedBuildNumber() {
        await browser.actions().mouseMove(element(by.css('.navbar-brand'))).perform();

        var buildLinks = element.all(By.css('.bb-buildid-link'));
        let finishedBuildCss = 'span.badge-status.results_SUCCESS, ' +
                               'span.badge-status.results_WARNINGS, ' +
                               'span.badge-status.results_FAILURE, ' +
                               'span.badge-status.results_SKIPPED, ' +
                               'span.badge-status.results_EXCEPTION, ' +
                               'span.badge-status.results_RETRY, ' +
                               'span.badge-status.results_CANCELLED ';
        let elements = await buildLinks.all(By.css(finishedBuildCss));
        if (elements.length === 0) {
            return 0;
        }
        return +await elements[0].getText();
    }


    async getBuildResult(buildNumber) {
        const matchElement = async (elem) => {
            return await elem.getText() == buildNumber.toString();
        };

        var buildLink = element.all(By.css('.bb-buildid-link')).filter(matchElement);
        if (await buildLink.count() == 0) {
            return "NOT FOUND";
        }

        var resultTypes = [
            ['.badge-status.results_SUCCESS', "SUCCESS"],
            ['.badge-status.results_WARNINGS', "WARNINGS"],
            ['.badge-status.results_FAILURE', "FAILURE"],
            ['.badge-status.results_SKIPPED', "SKIPPED"],
            ['.badge-status.results_EXCEPTION', "EXCEPTION"],
            ['.badge-status.results_RETRY', "RETRY"],
            ['.badge-status.results_CANCELLED', "CANCELLED"]
        ];

        for (let i = 0; i < resultTypes.length; i++) {
            var answer = buildLink.all(By.css(resultTypes[i][0]));
            if (await answer.count() > 0) {
                return resultTypes[i][1];
            }
        }
        return "NOT FOUND";
    }

    async waitBuildFinished(reference) {
        const self = this;
        async function buildCountIncrement() {
            let currentBuildCount = await self.getLastFinishedBuildNumber();
            return currentBuildCount == reference;
        }
        await bbrowser.wait(buildCountIncrement, "Build count did not increment");
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
        await bbrowser.wait(isInBuild, "Did not get into build");
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
