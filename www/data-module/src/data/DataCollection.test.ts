/*
  This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0. If a copy of the
  MPL was not distributed with this file, You can obtain one at https://mozilla.org/MPL/2.0/.

  Copyright Buildbot Team Members
*/

import {DataCollection} from "./DataCollection";
import {BaseClass} from "./classes/BaseClass";
import {IDataDescriptor} from "./classes/DataDescriptor";
import {WebSocketClient} from "./WebSocketClient";
import {MockWebSocket} from "./MockWebSocket";
import {Query} from "./DataQuery";
import {BaseDataAccessor, EmptyDataAccessor} from "./DataAccessor";

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
    it("initial data should not overwrite filtered data from ws", () => {
      const c = createCollection('tests', {testdata__eq: 0});
      c.listener({k: "tests/1/update", m: {testid: 1, testdata: 1}});
      c.initial([{
        testid: 1,
        testdata: 0
      }]);
      expect(c.array.length).toEqual(0);
    });

    it("initial data should not overwrite not filtered data from ws", () => {
      const c = createCollection('tests', {testdata__eq: 0});
      c.listener({k: "tests/1/update", m: {testid: 1, testdata: 0}});
      c.initial([{
        testid: 1,
        testdata: 1
      }]);
      expect(c.array.map(x => [x.testid, x.testdata])).toEqual([[1, 0]]);
    });

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
