// this file will contains the different generic functions which
// will be called by the different tests

import { BasePage } from "./base";
import { ExpectedConditions as EC } from 'protractor';
import { bbrowser } from '../utils';

export class ForcePage extends BasePage {
    constructor() {
        super();
    }

    async setInputText(cssLabel, value) {
        const setInputValue = element(By.css(`forcefield label[for=${cssLabel}] + div input`));
        await setInputValue.clear();
        await setInputValue.sendKeys(value);
        const inputValue = await setInputValue.getAttribute('value');
        expect(inputValue).toBe(value);
    }

    async setReason(reason) {
        await this.setInputText("reason", reason);
    }

    async setYourName(yourName) {
        await this.setInputText("username", yourName);
    }

    async setProjectName(projectName) {
        await this.setInputText("project", projectName);
    }

    async setBranchName(branchName) {
        await this.setInputText("branch", branchName);
    }

    async setRepo(repo) {
        await this.setInputText("repository", repo);
    }

    async setRevisionName(RevisionName) {
        await this.setInputText("revision", RevisionName);
    }

    async clickStartButton() {
        let button = this.getStartButton();
        await bbrowser.wait(EC.elementToBeClickable(button),
                            "start button not clickable");
        await button.click();
    }

    async clickStartButtonAndWaitRedirectToBuild() {
        let previousUrl = await browser.getCurrentUrl();
        await this.clickStartButton();
        await bbrowser.wait(EC.not(EC.urlIs(previousUrl)),
                            "failed to create a buildrequest");
        await bbrowser.wait(EC.not(EC.urlContains('redirect_to_build=true')),
                            "failed to create a build");
    }

    async clickCancelWholeQueue() {
        let button = this.getCancelWholeQueue();
        await bbrowser.wait(EC.elementToBeClickable(button),
                            "cancel whole queue button not clickable");
        await button.click();
    }

    getStartButton() {
        return element(By.buttonText('Start Build'));
    }

    getCancelButton() {
        return element(By.buttonText('Cancel'));
    }

    getCancelWholeQueue() {
        return element(By.buttonText('Cancel whole queue'));
    }

    getStopButton() {
        return element(By.buttonText('Stop'));
    }
}
