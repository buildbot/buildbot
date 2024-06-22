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

import {LogTextManager} from "./LogTextManager";
import {CancellablePromise} from "buildbot-data-js";

const getFakeData = (offset: number, limit: number) => {
  return new CancellablePromise((resolve, reject, onCancel) => {
    let resultString = '';
    for (let i = 0; i < limit; ++i) {
      resultString += "oaaaaa\n";
    }
    resolve({logchunks: [{content: resultString}]});
  });
}

type DataRequest = {offset: number, limit: number};
type GetFakeDataFn = (offest: number, limit: number) => CancellablePromise<any>;

function flushPromisesAndTimers() {
  jest.runAllTimers();
  return new Promise(resolve => setImmediate(resolve));
}

const createRecordingGetFakeData = () : [DataRequest[], GetFakeDataFn] => {
  const requests: DataRequest[] = [];
  const getFakeDataWrapper = (offset: number, limit: number) => {
    requests.push({offset: offset, limit: limit});
    return getFakeData(offset, limit);
  }
  return [requests, getFakeDataWrapper]
}

describe('LogTextManager', () => {
  describe('selectChunkDownloadRange', () => {
    it('empty downloaded range', () => {
      expect(LogTextManager.selectChunkDownloadRange(100, 200, 0, 0, 150, 160, 0, 200))
        .toEqual([100, 200]);
      expect(LogTextManager.selectChunkDownloadRange(100, 200, 20, 20, 150, 160, 0, 200))
        .toEqual([100, 200]);
    });
    it('empty downloaded range exceeds chunk limit', () => {
      expect(LogTextManager.selectChunkDownloadRange(100, 200, 0, 0, 155, 160, 0, 10))
        .toEqual([152, 162]);
      expect(LogTextManager.selectChunkDownloadRange(100, 200, 0, 0, 150, 160, 0, 10))
        .toEqual([150, 160]);
      expect(LogTextManager.selectChunkDownloadRange(100, 200, 0, 0, 140, 170, 0, 10))
        .toEqual([150, 160]);
      expect(LogTextManager.selectChunkDownloadRange(100, 200, 0, 0, 10, 30, 0, 10))
        .toEqual([100, 110]);
      expect(LogTextManager.selectChunkDownloadRange(100, 200, 0, 0, 220, 240, 0, 10))
        .toEqual([190, 200]);
    });
    it('non-overlapping ranges', () => {
      expect(LogTextManager.selectChunkDownloadRange(100, 200, 20, 30, 150, 160, 0, 200))
        .toEqual([100, 200]);
      expect(LogTextManager.selectChunkDownloadRange(100, 200, 200, 230, 150, 160, 0, 200))
        .toEqual([100, 200]);
    });
    it('non-overlapping ranges, but overlaps caching', () => {
      expect(LogTextManager.selectChunkDownloadRange(100, 200, 20, 30, 150, 160, 200, 200))
        .toEqual([30, 200]);
      expect(LogTextManager.selectChunkDownloadRange(100, 200, 20, 30, 150, 160, 200, 10))
        .toEqual([30, 40]);
      expect(LogTextManager.selectChunkDownloadRange(100, 200, 200, 230, 150, 160, 200, 200))
        .toEqual([100, 200]);
      expect(LogTextManager.selectChunkDownloadRange(100, 200, 200, 230, 150, 160, 200, 10))
        .toEqual([190, 200]);
    });
    it('non-overlapping ranges, range exceeds chunk limit', () => {
      expect(LogTextManager.selectChunkDownloadRange(100, 200, 0, 10, 155, 160, 0, 10))
        .toEqual([152, 162]);
      expect(LogTextManager.selectChunkDownloadRange(100, 200, 0, 10, 150, 160, 0, 10))
        .toEqual([150, 160]);
      expect(LogTextManager.selectChunkDownloadRange(100, 200, 0, 10, 140, 170, 0, 10))
        .toEqual([150, 160]);
      expect(LogTextManager.selectChunkDownloadRange(100, 200, 0, 10, 10, 30, 0, 10))
        .toEqual([100, 110]);
      expect(LogTextManager.selectChunkDownloadRange(100, 200, 0, 10, 220, 240, 0, 10))
        .toEqual([190, 200]);
    });
    it('download range in downloaded', () => {
      expect(LogTextManager.selectChunkDownloadRange(100, 200, 90, 230, 150, 160, 0, 200))
        .toEqual([0, 0]);
      expect(LogTextManager.selectChunkDownloadRange(100, 200, 100, 230, 150, 160, 0, 200))
        .toEqual([0, 0]);
      expect(LogTextManager.selectChunkDownloadRange(100, 200, 90, 200, 150, 160, 0, 200))
        .toEqual([0, 0]);
    });
    it('ranges partially overlap', () => {
      expect(LogTextManager.selectChunkDownloadRange(100, 200, 140, 210, 150, 160, 0, 200))
        .toEqual([100, 140]);
      expect(LogTextManager.selectChunkDownloadRange(100, 200, 90, 160, 150, 160, 0, 200))
        .toEqual([160, 200]);
    });
    it('ranges partially overlap, download range exceeds chunk limit', () => {
      expect(LogTextManager.selectChunkDownloadRange(100, 200, 140, 210, 150, 160, 0, 10))
        .toEqual([130, 140]);
      expect(LogTextManager.selectChunkDownloadRange(100, 200, 90, 160, 150, 160, 0, 10))
        .toEqual([160, 170]);
    });
    it('downloaded range in middle', () => {
      expect(LogTextManager.selectChunkDownloadRange(100, 200, 120, 180, 150, 160, 0, 200))
        .toEqual([180, 200]);
      expect(LogTextManager.selectChunkDownloadRange(100, 200, 120, 180, 175, 195, 0, 200))
        .toEqual([180, 200]);
      expect(LogTextManager.selectChunkDownloadRange(100, 200, 120, 180, 105, 125, 0, 200))
        .toEqual([100, 120]);
      expect(LogTextManager.selectChunkDownloadRange(100, 200, 120, 180, 105, 195, 0, 200))
        .toEqual([180, 200]);
    });
    it('downloaded range in middle, parts exceed limit', () => {
      expect(LogTextManager.selectChunkDownloadRange(100, 200, 120, 180, 150, 160, 0, 10))
        .toEqual([180, 190]);
      expect(LogTextManager.selectChunkDownloadRange(100, 200, 120, 180, 175, 195, 0, 10))
        .toEqual([180, 190]);
      expect(LogTextManager.selectChunkDownloadRange(100, 200, 120, 180, 105, 125, 0, 10))
        .toEqual([110, 120]);
      expect(LogTextManager.selectChunkDownloadRange(100, 200, 120, 180, 105, 195, 0, 10))
        .toEqual([180, 190]);
    });
  });

  describe('shouldKeepPendingRequest', () => {
    it('visible in downloaded', () => {
      expect(LogTextManager.shouldKeepPendingRequest(100, 200, false, 200, 300, 100, 150))
        .toEqual(true);
    });
    it('pinned downloaded', () => {
      expect(LogTextManager.shouldKeepPendingRequest(100, 200, true, 200, 300, 10, 20))
        .toEqual(true);
    });
    it('visible after downloaded', () => {
      expect(LogTextManager.shouldKeepPendingRequest(100, 200, false, 200, 300, 200, 250))
        .toEqual(true);
      expect(LogTextManager.shouldKeepPendingRequest(100, 200, false, 200, 220, 200, 250))
        .toEqual(true);
      expect(LogTextManager.shouldKeepPendingRequest(100, 200, false, 200, 220, 230, 250))
        .toEqual(false);
    });
    it('visible before downloaded', () => {
      expect(LogTextManager.shouldKeepPendingRequest(100, 200, false, 0, 100, 50, 150))
        .toEqual(true);
      expect(LogTextManager.shouldKeepPendingRequest(100, 200, false, 80, 100, 50, 150))
        .toEqual(true);
      expect(LogTextManager.shouldKeepPendingRequest(100, 200, false, 80, 100, 20, 50))
        .toEqual(false);
    });
  });

  describe("download", () => {
    beforeEach(() => {
      jest.useFakeTimers();
    });

    it('empty', async () => {
      const [dataRequests, getFakeDataWrapper] = createRecordingGetFakeData();

      const manager = new LogTextManager(
          getFakeDataWrapper, 's', 10, 20, 1000, 1000, 50, () => {});

      manager.setLogNumLines(0);
      manager.requestRows({
        overscanStartIndex: 0,
        overscanStopIndex: 20,
        visibleStartIndex: 0,
        visibleStopIndex: 20,
      });

      await flushPromisesAndTimers();
      expect(dataRequests).toEqual([]);
    });

    it('less than overscan', async () => {
      const [dataRequests, getFakeDataWrapper] = createRecordingGetFakeData();

      const manager = new LogTextManager(
          getFakeDataWrapper, 's', 10, 20, 1000, 1000, 50, () => {});

      manager.setLogNumLines(10);
      manager.requestRows({
        overscanStartIndex: 0,
        overscanStopIndex: 20,
        visibleStartIndex: 0,
        visibleStopIndex: 20,
      });

      await flushPromisesAndTimers();
      expect(dataRequests).toEqual([{offset: 0, limit: 10}]);
    });

    it('more than overscan', async () => {
      const [dataRequests, getFakeDataWrapper] = createRecordingGetFakeData();

      const manager = new LogTextManager(
          getFakeDataWrapper, 's', 10, 20, 1000, 1000, 50, () => {});

      manager.setLogNumLines(100);
      manager.requestRows({
        overscanStartIndex: 0,
        overscanStopIndex: 20,
        visibleStartIndex: 0,
        visibleStopIndex: 20,
      });

      await flushPromisesAndTimers();
      expect(dataRequests).toEqual([{offset: 0, limit: 40}]);
    });

    it('request outside log', async () => {
      const [dataRequests, getFakeDataWrapper] = createRecordingGetFakeData();

      const manager = new LogTextManager(
          getFakeDataWrapper, 's', 10, 20, 1000, 1000, 50, () => {});

      manager.setLogNumLines(100);
      manager.requestRows({
        overscanStartIndex: 200,
        overscanStopIndex: 220,
        visibleStartIndex: 200,
        visibleStopIndex: 220,
      });

      await flushPromisesAndTimers();
      expect(dataRequests).toEqual([]);
    });

    it('more than one request', async () => {
      const [dataRequests, getFakeDataWrapper] = createRecordingGetFakeData();

      const manager = new LogTextManager(
          getFakeDataWrapper, 's', 10, 20, 1000, 1000, 50, () => {});

      manager.setLogNumLines(1000);
      manager.requestRows({
        overscanStartIndex: 100,
        overscanStopIndex: 320,
        visibleStartIndex: 100,
        visibleStopIndex: 320,
      });

      await flushPromisesAndTimers();
      expect(dataRequests).toEqual([
          {offset: 185, limit: 50},
          {offset: 235, limit: 50},
          {offset: 285, limit: 50},
          {offset: 135, limit: 50},
          {offset: 85, limit: 50},
      ]);
    });
  });

  describe("search", () => {
    beforeEach(() => {
      jest.useFakeTimers();
    });

    it('no occurrences', async () => {
      const [dataRequests, getFakeDataWrapper] = createRecordingGetFakeData();

      const manager = new LogTextManager(
          getFakeDataWrapper, 's', 10, 20, 1000, 1000, 50, () => {});

      manager.setLogNumLines(100);
      manager.requestRows({
        overscanStartIndex: 0,
        overscanStopIndex: 20,
        visibleStartIndex: 0,
        visibleStopIndex: 20,
      });
      await flushPromisesAndTimers();
      expect(dataRequests).toEqual([
          {offset: 0, limit: 40}
      ]);

      manager.setSearchString("bbbbb");

      await flushPromisesAndTimers();
      expect(dataRequests).toEqual([
        {offset: 0, limit: 40},
        {offset: 40, limit: 50},
        {offset: 90, limit: 10},
      ]);
      expect(manager.totalSearchResultCount).toEqual(0);
    });

    it('with occurrences', async () => {
      const [dataRequests, getFakeDataWrapper] = createRecordingGetFakeData();

      const manager = new LogTextManager(
          getFakeDataWrapper, 's', 10, 20, 1000, 1000, 50, () => {});

      manager.setLogNumLines(100);
      manager.requestRows({
        overscanStartIndex: 0,
        overscanStopIndex: 20,
        visibleStartIndex: 0,
        visibleStopIndex: 20,
      });
      await flushPromisesAndTimers();
      expect(dataRequests).toEqual([
        {offset: 0, limit: 40}
      ]);

      manager.setSearchString("aaaaa");

      await flushPromisesAndTimers();
      expect(dataRequests).toEqual([
        {offset: 0, limit: 40},
        {offset: 40, limit: 50},
        {offset: 90, limit: 10},
      ]);
      expect(manager.totalSearchResultCount).toEqual(100);

      manager.setSearchString("aaAAa");

      expect(manager.totalSearchResultCount).toEqual(0);

      manager.setSearchCaseSensitivity(false);

      expect(manager.totalSearchResultCount).toEqual(100);

      manager.setSearchString("a{5}");

      expect(manager.totalSearchResultCount).toEqual(0);

      manager.setUseRegex(true);

      expect(manager.totalSearchResultCount).toEqual(100);
    });
  });
});
