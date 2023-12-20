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

export class HomePage {
  static async goto(page: Page) {
    await page.goto('/#/');
    await page.waitForURL(/\/#\/$/);
    await BasePage.waitUntilFinishedLoading(page);
  }

  static getBuilderCard(page: Page) {
    return page.locator(".bb-home-builder-card");
  }

  static async waitAllBuildsFinished(page: Page) {
    await HomePage.goto(page);
    await expect.poll(async () => {
      const text = await page.locator("h4").first().textContent();
      if (text === null) {
        return false;
      }
      return text.toLowerCase().indexOf("0 builds running") >= 0;
    }, {
      message: "builds are no longer running"
    }).toBeTruthy();
  }
}
