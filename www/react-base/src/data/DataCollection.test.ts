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

import DataCollection from "./DataCollection";
import BaseClass from "./classes/BaseClass";
import IDataDescriptor from "./classes/DataDescriptor";
import {WebSocketClient} from "./WebSocketClient";
import {MockWebSocket} from "./MockWebSocket";
import {Query} from "./DataQuery";
import BaseDataAccessor, {EmptyDataAccessor} from "./DataAccessor";

class TestDataClass extends BaseClass {
  testdata: string = '';
  testid: number = 0;

  constructor(accessor: BaseDataAccessor, endpoint: string, object: any) {
    super(accessor, endpoint, String(object.testid));
    this.update(object);
  }

  update(object: any) {
    this.testid = object.testid;
    this.testdata = object.testdata;
  }
}

class TestDescriptor implements IDataDescriptor<TestDataClass> {
  restArrayField = "tests";
  fieldId: string = 'testid';

  parse(accessor: BaseDataAccessor, endpoint: string, object: any) {
    return new TestDataClass(accessor, endpoint, object);
  }
}

describe('DataCollection', () => {
  function createCollection(restPath: string, query: Query) {
    const c = new DataCollection<TestDataClass>();
    c.open(restPath, query, new EmptyDataAccessor(), new TestDescriptor(),
      new WebSocketClient('url', (_) => new MockWebSocket()));
    return c;
  }

  beforeEach(() => {
    jest.useFakeTimers();
  });

  describe("simple collection", () => {

    it('should have a put function, which does not add twice for the same id', () => {
      const c = createCollection('tests', {});
      c.put({testid: 1});
      expect(c.array.length).toEqual(1);
      c.put({testid: 1});
      expect(c.array.length).toEqual(1);
      c.put({testid: 2});
      expect(c.array.length).toEqual(2);
    });

    it('should have a from function, which iteratively inserts data', () => {
      const c = createCollection('tests', {});
      c.from([
        {testid: 1},
        {testid: 2},
        {testid: 2}
      ]);
      expect(c.array.length).toEqual(2);
    });

    it("should order the updates correctly", () => {
      const c = createCollection('tests', {});
      c.listener({k: "tests/1/update", m: {testid: 1, testdata: 1}});
      c.initial([{
          testid: 1,
          testdata: 0
        }
      ]);
      expect(c.array[0].testdata).toEqual(1);
      c.listener({k: "tests/1/update", m: {testid: 1, testdata: 2}});
      expect(c.array[0].testdata).toEqual(2);
    });
  });

  describe("queried collection", () => {

    it('should have a from function, which iteratively inserts data', () => {
      const c = createCollection('tests', {order:'-testid', limit: 2});

      c.from([
        {testid: 1},
        {testid: 2},
        {testid: 2}
      ]);
      expect(c.array.length).toEqual(2);
      c.from([
        {testid: 3},
        {testid: 4},
        {testid: 5}
      ]);
      expect(c.array.length).toEqual(2);
      expect(c.array[0].id).toEqual("5");
      expect(c.array[1].id).toEqual("4");
    });
  });


  describe("singleid collection", () => {
    const c = createCollection('tests/1', {});

    it("should manage the updates correctly", () => {
      c.listener({k: "tests/1/update", m: {testid: 1, testdata: 1}});
      c.listener({k: "tests/2/update", m: {testid: 2, testdata: 2}});
      c.initial([{
          testid: 1,
          testdata: 0
        }
      ]);
      expect(c.array.length).toEqual(1);
      expect(c.array[0].testdata).toEqual(1);
      c.listener({k: "tests/1/update", m: {testid: 1, testdata: 2}});
      expect(c.array[0].testdata).toEqual(2);
    });
  });
});
