/*
  This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0. If a copy of the
  MPL was not distributed with this file, You can obtain one at https://mozilla.org/MPL/2.0/.

  Copyright Buildbot Team Members
*/

import {afterEach, beforeEach, describe, expect, it, vi} from "vitest";
import {BaseClass} from "./classes/BaseClass";
import {IDataDescriptor} from "./classes/DataDescriptor";
import {WebSocketClient} from "./WebSocketClient";
import {MockWebSocket} from "./MockWebSocket";
import {RequestQuery} from "./DataQuery";
import {BaseDataAccessor, IDataAccessor} from "./DataAccessor";
import {RestClient} from "./RestClient";
import {DataClient} from "./DataClient";
import MockAdapter from "axios-mock-adapter";
import axios from "axios";

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

  getProperties(query: RequestQuery = {}) {
    return this.getPropertiesImpl("properties", query);
  }

  toObject() {
    return {
      testid: this.testid,
      testdata: this.testdata,
    }
  }

  static getAll(accessor: IDataAccessor, query: RequestQuery = {}) {
    return accessor.get<TestDataClass>("tests", query, testDescriptor);
  }
}

class TestDescriptor implements IDataDescriptor<TestDataClass> {
  restArrayField = "tests";
  fieldId: string = 'testid';

  parse(accessor: BaseDataAccessor, endpoint: string, object: any) {
    return new TestDataClass(accessor, endpoint, object);
  }
}

const testDescriptor = new TestDescriptor();

describe('DataPropertiesCollection', () => {
  const rootUrl = 'http://test.example.com/api/';
  let mock : MockAdapter;
  let restClient: RestClient;
  let webSocket: MockWebSocket;
  let webSocketClient: WebSocketClient;
  let client: DataClient;

  beforeEach(() => {
    vi.useFakeTimers({ toFake: ['nextTick'] });
    mock = new MockAdapter(axios);
    restClient = new RestClient(rootUrl);
    webSocket = new MockWebSocket();
    webSocket.readyState = webSocket.OPEN;
    webSocketClient = new WebSocketClient('url', (_) => webSocket);
    client = new DataClient(restClient, webSocketClient);
  });

  afterEach(() => {
    mock.reset();
  });

  const flushPromisesAndTimers = async () => {
    await new Promise((resolve) => setTimeout(resolve, 0));
    await vi.runAllTimersAsync();
  }

  it("new properties to empty properties", async () => {
    mock.onGet(rootUrl + 'tests').reply(200, {tests: [
        {
          testid: 12,
          testdata: 'c12'
        }
      ]});

    const tests = TestDataClass.getAll(client.open());
    await flushPromisesAndTimers();

    expect(webSocket.parsedSendQueue).toEqual([{
      _id: 1,
      cmd: 'startConsuming',
      path: 'tests/*/*'
    }]);
    webSocket.clearSendQueue();
    webSocket.respond(JSON.stringify({_id: 1, msg: "OK", code: 200}));
    await flushPromisesAndTimers();

    expect(tests.array.map(e => e.toObject())).toEqual([
      {testid: 12, testdata: 'c12'},
    ]);

    mock.onGet(rootUrl + 'tests/12/properties').reply(200, {properties: [{}]});
    const properties = tests.array[0].getProperties();

    await flushPromisesAndTimers();

    expect(Object.fromEntries(properties.properties)).toEqual({});

    expect(webSocket.parsedSendQueue).toEqual([{
      _id: 2,
      cmd: 'startConsuming',
      path: 'tests/12/properties/*'
    }]);
    webSocket.clearSendQueue();

    webSocket.respond(JSON.stringify({_id: 2, msg: "OK", code: 200}));
    await flushPromisesAndTimers();

    // respond with new properties
    webSocket.respond(JSON.stringify({
      k: 'tests/12/properties/update',
      m: { prop1: 51, prop2: 'p52' }
    }));
    await flushPromisesAndTimers();

    expect(Object.fromEntries(properties.properties)).toEqual({prop1: 51, prop2: 'p52'});

    // respond with property updates
    webSocket.respond(JSON.stringify({
      k: 'tests/12/properties/update',
      m: { prop1: 52, prop2: 'p53', prop3: 3 }
    }));
    await flushPromisesAndTimers();

    expect(Object.fromEntries(properties.properties)).toEqual({prop1: 52, prop2: 'p53', prop3: 3});
  });

  it("new properties to non empty properties", async () => {
    mock.onGet(rootUrl + 'tests').reply(200, {tests: [
        {
          testid: 12,
          testdata: 'c12'
        }
      ]});

    const tests = TestDataClass.getAll(client.open());
    await flushPromisesAndTimers();

    expect(webSocket.parsedSendQueue).toEqual([{
      _id: 1,
      cmd: 'startConsuming',
      path: 'tests/*/*'
    }]);
    webSocket.clearSendQueue();
    webSocket.respond(JSON.stringify({_id: 1, msg: "OK", code: 200}));
    await flushPromisesAndTimers();

    expect(tests.array.map(e => e.toObject())).toEqual([
      {testid: 12, testdata: 'c12'},
    ]);

    mock.onGet(rootUrl + 'tests/12/properties').reply(200, {properties: [
      {
        prop1: 51,
        prop2: 'p52'
      }
    ]});

    const properties = tests.array[0].getProperties();

    await flushPromisesAndTimers();

    expect(webSocket.parsedSendQueue).toEqual([{
      _id: 2,
      cmd: 'startConsuming',
      path: 'tests/12/properties/*'
    }]);
    webSocket.clearSendQueue();

    webSocket.respond(JSON.stringify({_id: 2, msg: "OK", code: 200}));
    await flushPromisesAndTimers();

    expect(Object.fromEntries(properties.properties)).toEqual({prop1: 51, prop2: 'p52'});

    // respond with property updates
    webSocket.respond(JSON.stringify({
      k: 'tests/12/properties/update',
      m: { prop1: 52, prop2: 'p53', prop3: 3 }
    }));
    await flushPromisesAndTimers();

    expect(Object.fromEntries(properties.properties)).toEqual({prop1: 52, prop2: 'p53', prop3: 3});
  });
});
