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

import {test} from "@playwright/test";
import {ForcePage} from "./pages/force";
import {HomePage} from './pages/home';
import {BuilderPage} from './pages/builder';

test.describe('rebuilds', function() {
  test.afterEach(async ({page}) => {
    await HomePage.waitAllBuildsFinished(page);
  });

  test('should navigate to a dedicated build and to use the rebuild button',
      async ({page}) => {
    await BuilderPage.gotoBuildersList(page);
    await BuilderPage.goto(page, "runtests");
    const lastbuild = await BuilderPage.getLastFinishedBuildNumber(page);
    await BuilderPage.gotoForce(page, "runtests", "force");
    await ForcePage.clickStartButtonAndWaitRedirectToBuild(page);
    await BuilderPage.goto(page, "runtests");
    await BuilderPage.waitBuildFinished(page, lastbuild + 1);
    await BuilderPage.gotoBuild(page, "runtests", `${lastbuild + 1}`);
    await BuilderPage.clickRebuildButton(page);
    await BuilderPage.waitGoToBuild(page, lastbuild + 2);
  });
});
