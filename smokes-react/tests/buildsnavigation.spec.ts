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

import {expect, test} from "@playwright/test";
import {BasePage} from "./pages/base";
import {BuilderPage} from './pages/builder';
import {ForcePage} from "./pages/force";
import {HomePage} from './pages/home';

test.describe('previousnextlink', function() {
  test.afterEach(async ({page}) => {
    await HomePage.waitAllBuildsFinished(page);
  });

  test('should navigate in the builds history by using the previous next links',
      async ({page}) => {
    await BuilderPage.goto(page, "runtests");
    const lastbuild = await BuilderPage.getLastFinishedBuildNumber(page);
    // Build #1
    await BuilderPage.gotoForce(page, "runtests", "force");
    await ForcePage.clickStartButtonAndWaitRedirectToBuild(page);
    await BuilderPage.goto(page, "runtests");
    await BuilderPage.waitBuildFinished(page, lastbuild + 1);
    // Build #2
    await BuilderPage.gotoForce(page, "runtests", "force");
    await ForcePage.clickStartButtonAndWaitRedirectToBuild(page);
    await BuilderPage.goto(page, "runtests");
    await BuilderPage.waitBuildFinished(page, lastbuild + 2);
    await BuilderPage.gotoBuild(page, "runtests", `${lastbuild + 2}`);
    const lastBuildURL = page.url();
    await BuilderPage.clickPreviousButtonAndWait(page);
    await expect.poll(() => page.url()).not.toMatch(lastBuildURL);
    await BuilderPage.clickNextButtonAndWait(page);
    await expect.poll(() => page.url()).toMatch(lastBuildURL);
  });
});

test.describe('forceandstop', function() {
  test('should create a build with a dedicated reason and stop it during execution',
      async ({page}) => {
    await BuilderPage.gotoForce(page, "slowruntests", "force");
    await ForcePage.clickStartButtonAndWaitRedirectToBuild(page);
    await BuilderPage.clickStopButton(page);

    await expect.poll(async () => {
      return (await page.locator(".bb-build-summary-details")
        .locator('.bb-badge-status.results_CANCELLED').count()) !== 0;
    }, {
      message: "canceled build"
    }).toBeTruthy();
  });
});
