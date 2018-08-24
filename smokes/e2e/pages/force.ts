// this file will contains the different generic functions which
// will be called by the different tests

import { BasePage } from "./base";

export class ForcePage extends BasePage {
    constructor() {
        {
          super();
          let thisFn = (() => { return this; }).toString();
          let thisName = thisFn.slice(thisFn.indexOf('return') + 6 + 1, thisFn.indexOf(';')).trim();
        }
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

    getStartButton() {
        return element(By.buttonText('Start Build'));
    }

    getCancelButton() {
        return element(By.buttonText('Cancel'));
    }

    getCancelWholeQueue() {
        return element(By.buttonText('Cancel Whole Queue'));
    }

    getStopButton() {
        return element(By.buttonText('Stop'));
    }
}
