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
import {BuilderPage} from './pages/builder';
import {ForcePage} from "./pages/force";
import {HomePage} from './pages/home';

test.describe('home page', function() {
  test('should go to the home page and check if panel with builder name exists', async ({page}) => {
    const builderName = {
      0 : "runtests"
    };
    await BuilderPage.goto(page, "runtests");
    const buildnumber = await BuilderPage.getLastFinishedBuildNumber(page);
    await BuilderPage.gotoForce(page, "runtests", "force");
    await ForcePage.clickStartButtonAndWaitRedirectToBuild(page);
    await BuilderPage.goto(page, "runtests");
    await BuilderPage.waitBuildFinished(page, buildnumber + 1);
    await HomePage.goto(page);
    const card0 = HomePage.getBuilderCard(page).first().locator(".card-header");
    expect(await card0.textContent()).toContain(builderName[0]);
  });
});
