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

import {Build} from "../../data/classes/Build";
import renderer from 'react-test-renderer';
import BuildSticker from "./BuildSticker";
import {Builder} from "../../data/classes/Builder";
import {FAILURE, SUCCESS} from "../../util/Results";
import {MemoryRouter} from "react-router-dom";
import TimeStore from "../../stores/TimeStore";
import { TimeContext } from "../../contexts/Time";

function assertBuildStickerRenderSnapshot(build: Build, builder: Builder) {
  const timeStore = new TimeStore();
  timeStore.setTimeFromString("2022-01-01T00:00:00.000Z");

  const component = renderer.create(
    <MemoryRouter>
      <TimeContext.Provider value={timeStore}>
        <BuildSticker build={build} builder={builder}/>
      </TimeContext.Provider>
    </MemoryRouter>
  );
  expect(component.toJSON()).toMatchSnapshot();
}

describe('buildsticker component', function() {
  it('simple', () => {
    const build: Build = {
      buildid: 3,
      builderid: 2,
      number: 1,
      complete: false,
      started_at: null,
      results: -1,
      state_string: null,
    } as any;

    const builder: Builder = {
      builderid: 2
    } as any;

    assertBuildStickerRenderSnapshot(build, builder);
  });

  it('pending', () => {
    const build: Build = {
      buildid: 3,
      builderid: 2,
      number: 1,
      complete: false,
      started_at: 20,
      results: -1,
      state_string: 'pending',
    } as any;

    const builder: Builder = {
      builderid: 2
    } as any;

    assertBuildStickerRenderSnapshot(build, builder);
  });

  it('success', () => {
    const build: Build = {
      buildid: 3,
      builderid: 2,
      number: 1,
      complete: true,
      started_at: 20,
      complete_at: 30,
      results: SUCCESS,
      state_string: 'finished',
    } as any;

    const builder: Builder = {
      builderid: 2
    } as any;

    assertBuildStickerRenderSnapshot(build, builder);
  });

  it('failed', () => {
    const build: Build = {
      buildid: 3,
      builderid: 2,
      number: 1,
      complete: true,
      started_at: 20,
      complete_at: 30,
      results: FAILURE,
      state_string: 'failed',
    } as any;

    const builder: Builder = {
      builderid: 2
    } as any;

    assertBuildStickerRenderSnapshot(build, builder);
  });
});
