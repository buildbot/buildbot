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

describe('LogTextManager', () => {
  describe('selectChunkDownloadRange', () => {
    it('empty downloaded range', () => {
      expect(LogTextManager.selectChunkDownloadRange(100, 200, 0, 0, 150, 160))
        .toEqual([100, 200]);
      expect(LogTextManager.selectChunkDownloadRange(100, 200, 20, 20, 150, 160))
        .toEqual([100, 200]);
    });
    it('non-overlapping ranges', () => {
      expect(LogTextManager.selectChunkDownloadRange(100, 200, 20, 30, 150, 160))
        .toEqual([100, 200]);
      expect(LogTextManager.selectChunkDownloadRange(100, 200, 200, 230, 150, 160))
        .toEqual([100, 200]);
    });
    it('download range in downloaded', () => {
      expect(LogTextManager.selectChunkDownloadRange(100, 200, 90, 230, 150, 160))
        .toEqual([0, 0]);
      expect(LogTextManager.selectChunkDownloadRange(100, 200, 100, 230, 150, 160))
        .toEqual([0, 0]);
      expect(LogTextManager.selectChunkDownloadRange(100, 200, 90, 200, 150, 160))
        .toEqual([0, 0]);
    });
    it('ranges partially overlap', () => {
      expect(LogTextManager.selectChunkDownloadRange(100, 200, 110, 210, 150, 160))
        .toEqual([100, 110]);
      expect(LogTextManager.selectChunkDownloadRange(100, 200, 90, 190, 150, 160))
        .toEqual([190, 200]);
    });
    it('downloaded range in middle', () => {
      expect(LogTextManager.selectChunkDownloadRange(100, 200, 110, 190, 150, 160))
        .toEqual([190, 200]);
      expect(LogTextManager.selectChunkDownloadRange(100, 200, 110, 190, 185, 195))
        .toEqual([190, 200]);
      expect(LogTextManager.selectChunkDownloadRange(100, 200, 110, 190, 105, 115))
        .toEqual([100, 110]);
      expect(LogTextManager.selectChunkDownloadRange(100, 200, 110, 190, 105, 195))
        .toEqual([100, 200]);
    });
  });

  describe('shouldKeepPendingRequest', () => {
    it('visible in downloaded', () => {
      expect(LogTextManager.shouldKeepPendingRequest(100, 200, 200, 300, 100, 150))
        .toEqual(true);
    });
    it('visible after downloaded', () => {
      expect(LogTextManager.shouldKeepPendingRequest(100, 200, 200, 300, 200, 250))
        .toEqual(true);
      expect(LogTextManager.shouldKeepPendingRequest(100, 200, 200, 220, 200, 250))
        .toEqual(true);
      expect(LogTextManager.shouldKeepPendingRequest(100, 200, 200, 220, 230, 250))
        .toEqual(false);
    });
    it('visible before downloaded', () => {
      expect(LogTextManager.shouldKeepPendingRequest(100, 200, 0, 100, 50, 150))
        .toEqual(true);
      expect(LogTextManager.shouldKeepPendingRequest(100, 200, 80, 100, 50, 150))
        .toEqual(true);
      expect(LogTextManager.shouldKeepPendingRequest(100, 200, 80, 100, 20, 50))
        .toEqual(false);
    });
  });
});
