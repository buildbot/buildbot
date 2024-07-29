/*
  This file is part of Buildbot.  Buildbot is free software: you can
  redistribute it and/or modify it under the terms of the GNU General Public
  License as published by the Free Software Foundation, version 2.

  This program is distributed in the hope that it will be useful, but WITHOUT
  ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
  FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more
  details.

  You should have received a copy of the GNU General Public License along with
  this program; if not, write to the Free Software Foundation, Inc., 51
  Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.

  Copyright Buildbot Team Members
*/

import {expect, Page} from "@playwright/test";
import {BasePage} from "./base";

export class ForcePage {
  static async setInputText(page: Page, fieldName: string, value: string) {
    const input = page.getByTestId(`force-field-${fieldName}`);
    await expect.poll(() => input.count()).toEqual(1);
    await input.fill(value);
  }

  static async setReason(page: Page, value: string) {
    await ForcePage.setInputText(page, "reason", value);
  }

  static async setYourName(page: Page, value: string) {
    await ForcePage.setInputText(page, "username", value);
  }

  static async setProjectName(page: Page, value: string) {
    await ForcePage.setInputText(page, "project", value);
  }

  static async setBranchName(page: Page, value: string) {
    await ForcePage.setInputText(page, "branch", value);
  }

  static async setRepo(page: Page, value: string) {
    await ForcePage.setInputText(page, "repository", value);
  }

  static async setRevisionName(page: Page, value: string) {
    await ForcePage.setInputText(page, "revision", value);
  }

  static async clickStartButtonAndWait(page: Page) {
    await BasePage.waitUntilUrlChanged(page, async () => {
      await page.locator('button:text("Start build")').click();
    });
  }

  static async clickStartButtonAndWaitRedirectToBuild(page: Page) {
    await ForcePage.clickStartButtonAndWait(page);
    await page.waitForURL(/\/#\/builders\/[0-9]\/builds\/[0-9]+$/);
    await BasePage.waitUntilFinishedLoading(page);
  }

  static async clickCancelWholeQueue(page: Page) {
    await ForcePage.getCancelWholeQueue(page).click();
  }

  static async clickCancelButton(page: Page) {
    await page.locator('button:text("Cancel")').click();
  }

  static getCancelWholeQueue(page: Page) {
    return page.locator('button:text("Cancel whole queue")');
  }

  static getStopButton(page: Page) {
    return page.locator('button:text("Stop")');
  }
}
