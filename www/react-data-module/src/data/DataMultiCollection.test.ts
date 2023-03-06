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

import BaseClass from "./classes/BaseClass";
import IDataDescriptor from "./classes/DataDescriptor";
import {WebSocketClient} from "./WebSocketClient";
import {MockWebSocket} from "./MockWebSocket";
import {RequestQuery} from "./DataQuery";
import BaseDataAccessor, {IDataAccessor} from "./DataAccessor";
import RestClient from "./RestClient";
import DataClient from "./DataClient";
import MockAdapter from "axios-mock-adapter";
import axios from "axios";

class TestParentClass extends BaseClass {
  parentdata: string = '';
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
    }
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
  fieldId: string = 'parentid';

  parse(accessor: BaseDataAccessor, endpoint: string, object: any) {
    return new TestParentClass(accessor, endpoint, object);
  }
}

const parentDescriptor = new ParentDescriptor();

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

  toObject() {
    return {
      testid: this.testid,
      testdata: this.testdata,
    }
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

describe('DataMultiCollection', () => {
  const rootUrl = 'http://test.example.com/api/';
  let mock : MockAdapter;
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
    webSocketClient = new WebSocketClient('url', (_) => webSocket);
    client = new DataClient(restClient, webSocketClient);
  });

  afterEach(() => {
    mock.reset();
  });

  function flushPromisesAndTimers() {
    jest.runAllTimers();
    return new Promise(resolve => setImmediate(resolve));
  }

  it("new objects to empty collection", async () => {
    mock.onGet(rootUrl + 'parents').reply(200, {parents: []});

    // request all parents and all tests
    const parents = TestParentClass.getAll(client.open());
    const tests = parents.getRelated((p) => p.getTests());

    await flushPromisesAndTimers();

    expect(webSocket.parsedSendQueue).toEqual([{
      _id: 1,
      cmd: 'startConsuming',
      path: 'parents/*/*'
    }]);
    webSocket.clearSendQueue();
    expect(parents.array.length).toEqual(0);
    expect(tests.byParentId.size).toEqual(0);

    webSocket.respond(JSON.stringify({_id: 1, msg: "OK", code: 200}));
    await flushPromisesAndTimers();

    // respond with one parent
    mock.onGet(rootUrl + 'parents/12/tests').reply(200, {tests: []});
    webSocket.respond(JSON.stringify({
      k: 'parents/12/new',
      m: { parentid: 12, parentdata: 'p12' }
    }));

    await flushPromisesAndTimers();

    expect(webSocket.parsedSendQueue).toEqual([{
      _id: 2,
      cmd: 'startConsuming',
      path: 'parents/12/tests/*/*'
    }]);
    webSocket.clearSendQueue();

    expect(parents.array.map(e => e.toObject())).toEqual([
      {parentid: 12, parentdata: 'p12'},
    ]);
    expect(tests.byParentId.size).toEqual(1);
    expect(tests.byParentId.get('12')!.array.length).toEqual(0);

    webSocket.respond(JSON.stringify({_id: 2, msg: "OK", code: 200}));
    await flushPromisesAndTimers();

    // respond with a child
    webSocket.respond(JSON.stringify({
      k: 'parents/12/tests/51/new',
      m: { testid: 51, testdata: 'c51' }
    }));

    await flushPromisesAndTimers();
    expect(parents.array.map(e => e.toObject())).toEqual([
      {parentid: 12, parentdata: 'p12'},
    ]);
    expect(tests.byParentId.get('12')!.array.map(e => e.toObject())).toEqual([
      {testid: 51, testdata: 'c51'},
    ]);

    // respond with another child
    webSocket.respond(JSON.stringify({
      k: 'parents/12/tests/52/new',
      m: { testid: 52, testdata: 'c52' }
    }));

    await flushPromisesAndTimers();
    expect(parents.array.map(e => e.toObject())).toEqual([
      {parentid: 12, parentdata: 'p12'},
    ]);
    expect(tests.byParentId.get('12')!.array.map(e => e.toObject())).toEqual([
      {testid: 51, testdata: 'c51'},
      {testid: 52, testdata: 'c52'},
    ]);

    // respond with another parent
    mock.onGet(rootUrl + 'parents/13/tests').reply(200, {tests: []});
    webSocket.respond(JSON.stringify({
      k: 'parents/13/new',
      m: { parentid: 13, parentdata: 'p13' }
    }));

    await flushPromisesAndTimers();

    expect(webSocket.parsedSendQueue).toEqual([{
      _id: 3,
      cmd: 'startConsuming',
      path: 'parents/13/tests/*/*'
    }]);
    webSocket.clearSendQueue();

    expect(parents.array.length).toEqual(2);

    webSocket.respond(JSON.stringify({_id: 3, msg: "OK", code: 200}));
    await flushPromisesAndTimers();

    // respond with another child for second parent
    webSocket.respond(JSON.stringify({
      k: 'parents/13/tests/61/new',
      m: { testid: 61, testdata: 'c61' }
    }));

    await flushPromisesAndTimers();
    expect(parents.array.map(e => e.toObject())).toEqual([
      {parentid: 12, parentdata: 'p12'},
      {parentid: 13, parentdata: 'p13'},
    ]);
    expect(tests.byParentId.size).toEqual(2);
    expect(tests.byParentId.get('12')!.array.map(e => e.toObject())).toEqual([
      {testid: 51, testdata: 'c51'},
      {testid: 52, testdata: 'c52'},
    ]);
    expect(tests.byParentId.get('13')!.array.map(e => e.toObject())).toEqual([
      {testid: 61, testdata: 'c61'},
    ]);
  });

  it("new objects to non-empty collection", async () => {
    mock.onGet(rootUrl + 'parents').reply(200, {parents: [
        {
          parentid: 12,
          parentdata: 'p12'
        }
      ]});
    mock.onGet(rootUrl + 'parents/12/tests').reply(200, {tests: [
        {
          testid: 51,
          testdata: 'c51'
        }
      ]});
    mock.onGet(rootUrl + 'parents/13/tests').reply(200, {tests: [
        {
          testid: 53,
          testdata: 'c53'
        }
      ]});

    // request all parents and all tests
    const parents = TestParentClass.getAll(client.open());
    const tests = parents.getRelated(p => p.getTests());

    await flushPromisesAndTimers();

    expect(webSocket.parsedSendQueue).toEqual([{
      _id: 1,
      cmd: 'startConsuming',
      path: 'parents/*/*'
    }]);
    webSocket.clearSendQueue();

    webSocket.respond(JSON.stringify({_id: 1, msg: "OK", code: 200}));
    await flushPromisesAndTimers();

    expect(webSocket.parsedSendQueue).toEqual([{
      _id: 2,
      cmd: 'startConsuming',
      path: 'parents/12/tests/*/*'
    }]);
    webSocket.clearSendQueue();

    webSocket.respond(JSON.stringify({_id: 2, msg: "OK", code: 200}));
    await flushPromisesAndTimers();

    expect(parents.array.map(e => e.toObject())).toEqual([
      {parentid: 12, parentdata: 'p12'},
    ]);
    expect(tests.byParentId.size).toEqual(1);
    expect(tests.byParentId.get('12')!.array.map(e => e.toObject())).toEqual([
      {testid: 51, testdata: 'c51'},
    ]);

    // respond with a child
    webSocket.respond(JSON.stringify({
      k: 'parents/12/tests/51/new',
      m: { testid: 52, testdata: 'c52' }
    }));

    await flushPromisesAndTimers();

    expect(parents.array.map(e => e.toObject())).toEqual([
      {parentid: 12, parentdata: 'p12'},
    ]);
    expect(tests.byParentId.get('12')!.array.map(e => e.toObject())).toEqual([
      {testid: 51, testdata: 'c51'},
      {testid: 52, testdata: 'c52'},
    ]);

    // respond with a parent (which immediately has a child)
    mock.onGet(rootUrl + 'tests/13').reply(200, {tests: []});
    webSocket.respond(JSON.stringify({
      k: 'parents/13/new',
      m: { parentid: 13, parentdata: 'p13' }
    }));

    await flushPromisesAndTimers();

    expect(webSocket.parsedSendQueue).toEqual([{
      _id: 3,
      cmd: 'startConsuming',
      path: 'parents/13/tests/*/*'
    }]);
    webSocket.clearSendQueue();

    webSocket.respond(JSON.stringify({_id: 3, msg: "OK", code: 200}));
    await flushPromisesAndTimers();

    expect(parents.array.map(e => e.toObject())).toEqual([
      {parentid: 12, parentdata: 'p12'},
      {parentid: 13, parentdata: 'p13'},
    ]);
    expect(tests.byParentId.get('12')!.array.map(e => e.toObject())).toEqual([
      {testid: 51, testdata: 'c51'},
      {testid: 52, testdata: 'c52'},
    ]);
    expect(tests.byParentId.get('13')!.array.map(e => e.toObject())).toEqual([
      {testid: 53, testdata: 'c53'},
    ]);

    // respond with another child
    webSocket.respond(JSON.stringify({
      k: 'parents/13/tests/54/new',
      m: { testid: 54, testdata: 'c54' }
    }));

    await flushPromisesAndTimers();
    expect(parents.array.map(e => e.toObject())).toEqual([
      {parentid: 12, parentdata: 'p12'},
      {parentid: 13, parentdata: 'p13'},
    ]);
    expect(tests.byParentId.get('12')!.array.map(e => e.toObject())).toEqual([
      {testid: 51, testdata: 'c51'},
      {testid: 52, testdata: 'c52'},
    ]);
    expect(tests.byParentId.get('13')!.array.map(e => e.toObject())).toEqual([
      {testid: 53, testdata: 'c53'},
      {testid: 54, testdata: 'c54'},
    ]);
  });
});
