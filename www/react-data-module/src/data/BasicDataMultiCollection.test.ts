/*
  This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0. If a copy of the
  MPL was not distributed with this file, You can obtain one at https://mozilla.org/MPL/2.0/.

  Copyright Buildbot Team Members
*/

import { BaseClass } from "./classes/BaseClass";
import { IDataDescriptor } from "./classes/DataDescriptor";
import { WebSocketClient } from "./WebSocketClient";
import { MockWebSocket } from "./MockWebSocket";
import { RequestQuery } from "./DataQuery";
import { BaseDataAccessor, IDataAccessor } from "./DataAccessor";
import MockAdapter from "axios-mock-adapter";
import { RestClient } from "./RestClient";
import { DataClient } from "./DataClient";
import axios from "axios";
import { observable } from "mobx";

class TestParentClass extends BaseClass {
  parentdata: string = "";
  parentid: number = 0;

  constructor(accessor: BaseDataAccessor, endpoint: string, object: any) {
    super(accessor, endpoint, String(object.parentid));
    this.update(object);
  }

  update(object: any) {
    this.parentid = object.parentid;
    this.parentdata = object.parentdata;
  }

  toObject() {
    return {
      parentid: this.parentid,
      parentdata: this.parentdata,
    };
  }

  getTests(query: RequestQuery = {}) {
    return this.get<TestDataClass>("tests", query, testDescriptor);
  }

  static getAll(accessor: IDataAccessor, query: RequestQuery = {}) {
    return accessor.get<TestParentClass>("parents", query, parentDescriptor);
  }
}

class ParentDescriptor implements IDataDescriptor<TestParentClass> {
  restArrayField = "parents";
  fieldId: string = "parentid";

  parse(accessor: BaseDataAccessor, endpoint: string, object: any) {
    return new TestParentClass(accessor, endpoint, object);
  }
}

const parentDescriptor = new ParentDescriptor();

class TestDataClass extends BaseClass {
  testdata: string = "";
  testid: number = 0;

  constructor(accessor: BaseDataAccessor, endpoint: string, object: any) {
    super(accessor, endpoint, String(object.testid));
    this.update(object);
  }

  update(object: any) {
    this.testid = object.testid;
    this.testdata = object.testdata;
  }

  toObject() {
    return {
      testid: this.testid,
      testdata: this.testdata,
    };
  }
}

class TestDescriptor implements IDataDescriptor<TestDataClass> {
  restArrayField = "tests";
  fieldId: string = "testid";

  parse(accessor: BaseDataAccessor, endpoint: string, object: any) {
    return new TestDataClass(accessor, endpoint, object);
  }
}

const testDescriptor = new TestDescriptor();
describe("BasicDataMultiCollection", () => {
  const rootUrl = "http://test.example.com/api/";
  let mock: MockAdapter;
  let restClient: RestClient;
  let webSocket: MockWebSocket;
  let webSocketClient: WebSocketClient;
  let client: DataClient;

  beforeEach(() => {
    jest.useFakeTimers();
    mock = new MockAdapter(axios);
    restClient = new RestClient(rootUrl);
    webSocket = new MockWebSocket();
    webSocket.readyState = webSocket.OPEN;
    webSocketClient = new WebSocketClient("url", (_) => webSocket);
    client = new DataClient(restClient, webSocketClient);
  });

  afterEach(() => {
    mock.reset();
  });

  function flushPromisesAndTimers() {
    jest.runAllTimers();
    return new Promise((resolve) => setImmediate(resolve));
  }

  function mockParentAndChild() {
    mock.onGet(rootUrl + "parents").reply(200, {
      parents: [
        {
          parentid: 12,
          parentdata: "p12",
        },
        {
          parentid: 13,
          parentdata: "p13",
        },
      ],
    });
    mock.onGet(rootUrl + "parents/12/tests").reply(200, {
      tests: [
        {
          testid: 51,
          testdata: "c51",
        },
      ],
    });
    mock.onGet(rootUrl + "parents/13/tests").reply(200, {
      tests: [
        {
          testid: 53,
          testdata: "c53",
        },
      ],
    });
  }

  it("new objects to empty collection", async () => {
    mockParentAndChild();

    // request all parents and all tests
    const parents = TestParentClass.getAll(client.open());
    const tests = parents.getRelatedOfFiltered(observable(["12"]), (p) => p.getTests());

    await flushPromisesAndTimers();

    expect(webSocket.parsedSendQueue).toEqual([{
      _id: 1,
      cmd: 'startConsuming',
      path: 'parents/*/*'
    }]);
    webSocket.clearSendQueue();

    webSocket.respond(JSON.stringify({_id: 1, msg: "OK", code: 200}));
    await flushPromisesAndTimers();

    expect(webSocket.parsedSendQueue).toEqual([
      {
        _id: 2,
        cmd: 'startConsuming',
        path: 'parents/12/tests/*/*'
      }
    ]);
    webSocket.clearSendQueue();

    webSocket.respond(JSON.stringify({_id: 2, msg: "OK", code: 200}));
    await flushPromisesAndTimers();

    expect(parents.array.map(e => e.toObject())).toEqual([
      {parentid: 12, parentdata: 'p12'},
      {parentid: 13, parentdata: 'p13'},
    ]);
    expect(tests.byParentId.size).toEqual(1);
    expect(tests.byParentId.get('12')!.array.map(e => e.toObject())).toEqual([
      {testid: 51, testdata: 'c51'},
    ]);
  });

  it("should return nothing on getRelatedOfFiltered with empty filteredIds", async () => {
    mockParentAndChild();

    // request all parents then no tests
    const parents = TestParentClass.getAll(client.open());
    const tests = parents.getRelatedOfFiltered(observable([]), (p) => p.getTests());

    await flushPromisesAndTimers();

    expect(webSocket.parsedSendQueue).toEqual([{
      _id: 1,
      cmd: 'startConsuming',
      path: 'parents/*/*'
    }]);
    webSocket.clearSendQueue();

    webSocket.respond(JSON.stringify({_id: 1, msg: "OK", code: 200}));
    await flushPromisesAndTimers();

    expect(webSocket.parsedSendQueue).toEqual([]);
    webSocket.clearSendQueue();

    webSocket.respond(JSON.stringify({_id: 2, msg: "OK", code: 200}));
    await flushPromisesAndTimers();

    expect(parents.array.map(e => e.toObject())).toEqual([
      {parentid: 12, parentdata: 'p12'},
      {parentid: 13, parentdata: 'p13'},
    ]);
    expect(tests.byParentId.size).toEqual(0);
  });
});
