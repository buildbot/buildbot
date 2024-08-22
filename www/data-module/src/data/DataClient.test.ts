/*
  This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0. If a copy of the
  MPL was not distributed with this file, You can obtain one at https://mozilla.org/MPL/2.0/.

  Copyright Buildbot Team Members
*/

import {afterEach, beforeEach, describe, expect, it, vi} from "vitest";
import axios from "axios";
import {WebSocketClient} from "./WebSocketClient";
import {MockWebSocket} from "./MockWebSocket";
import MockAdapter from "axios-mock-adapter";
import {DataClient} from "./DataClient";
import {RestClient} from "./RestClient";
import {BaseClass} from "./classes/BaseClass";
import {IDataDescriptor} from "./classes/DataDescriptor";
import {MockDataClient} from "./MockDataClient";
import {BaseDataAccessor} from "./DataAccessor";

class TestDataClass extends BaseClass {
  testdata!: string;
  testid!: number;

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
      testdata: this.testdata
    };
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

describe('Data service', () => {
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

  describe('get()', () => {
    it('should call get for the rest api endpoint', async () => {
      mock.onGet(rootUrl + 'tests').reply(200, {tests: [
          {testid: 1, testdata: 'abc1'},
          {testid: 2, testdata: 'abc2'},
        ]});

      const ret = client.get<TestDataClass>('tests', client.open(), testDescriptor, {}, false);
      await flushPromisesAndTimers();
      expect(ret.array.map(e => e.toObject())).toEqual([
        {testid: 1, testdata: 'abc1'},
        {testid: 2, testdata: 'abc2'},
      ]);
      expect(mock.history.get.length).toEqual(1);
    });

    it('should send startConsuming with the socket path', async () => {
      mock.onGet(rootUrl + 'tests').reply(200, {tests: []});
      mock.onGet(rootUrl + 'tests/1').reply(200, {tests: [
          {testid: 1, testdata: 'abc1'},
        ]});

      const data = client.open();

      data.get<TestDataClass>('tests', {}, testDescriptor);
      await flushPromisesAndTimers();
      expect(webSocket.parsedSendQueue).toEqual([{
        _id: 1,
        cmd: 'startConsuming',
        path: 'tests/*/*'
      }]);
      webSocket.clearSendQueue();

      data.get<TestDataClass>('tests/1', {}, testDescriptor);
      await flushPromisesAndTimers();
      expect(webSocket.parsedSendQueue).toEqual([{
        _id: 2,
        cmd: 'startConsuming',
        path: 'tests/1/*'
      }]);
      webSocket.clearSendQueue();

      // get same item again, it should not register again
      data.get<TestDataClass>('tests/1', {}, testDescriptor);
      expect(webSocket.parsedSendQueue).toEqual([])

      // now we close the accessor, and we should send stopConsuming
      data.close();
      expect(webSocket.parsedSendQueue).toEqual([{
          _id: 3,
          cmd: 'stopConsuming',
          path: 'tests/*/*'
        }, {
          _id: 4,
          cmd: 'stopConsuming',
          path: 'tests/1/*'
        }
      ]);
    });

    it('should not call startConsuming when {subscribe: false} is passed in', async () => {
      mock.onGet(rootUrl + 'tests').reply(200, {tests: []});

      const data = client.open();
      data.get<TestDataClass>('tests', {subscribe: false}, testDescriptor);
      await flushPromisesAndTimers();
      expect(webSocket.parsedSendQueue).toEqual([]);
    });

    it('should add the new instance on /new WebSocket message', async () => {
      mock.onGet(rootUrl + 'tests').reply(200, {tests: []});

      const data = client.open();
      const collection = data.get<TestDataClass>('tests', {}, testDescriptor);
      await flushPromisesAndTimers();
      expect(webSocket.parsedSendQueue).toEqual([{
        _id: 1,
        cmd: 'startConsuming',
        path: 'tests/*/*'
      }]);
      webSocket.respond(JSON.stringify({_id: 1, msg: "OK", code: 200}));
      webSocket.respond(JSON.stringify({
        k: 'tests/111/new',
        m: { testid: 111, testdata: 'abcd' }
      }));
      await flushPromisesAndTimers();
      expect(collection.array[0].toObject()).toEqual({
        testid: 111,
        testdata: 'abcd'
      });
      expect(mock.history.get.map(r => r.url)).toEqual([rootUrl + "tests"]);
    });
  });

  describe('control(method, params)', () =>
    it('should send a jsonrpc message using POST', () => {
      mock.onPost(rootUrl + 'tests/1').reply(200, {});

      const method = 'force';
      const params = {a: "1"};
      client.control("tests/1", method, params);
      expect(mock.history.post[0].url).toEqual(rootUrl + "tests/1");
      expect(mock.history.post[0].data).toEqual(JSON.stringify({
        id: 1,
        jsonrpc: '2.0',
        method,
        params
      }));
    })
  );

  describe('open()', () => {
    it('should call unsubscribe on each subscribed collection on close', async () => {
      mock.onGet(rootUrl + '/tests').reply(200, {tests: [
          {testid: 1, testdata: 'abc1'},
          {testid: 2, testdata: 'abc2'},
          {testid: 3, testdata: 'abc3'},
        ]});
      const data = client.open();
      const collection = data.get<TestDataClass>('/tests', {subscribe: false}, testDescriptor);
      await flushPromisesAndTimers();
      expect(collection.array.length).toBe(3);
      const spyClose = vi.spyOn(collection, 'close');
      data.close();
      expect(collection.close).toHaveBeenCalled();
    });
  });

  describe('when()', () =>
    it('should autopopulate ids', async () => {
      const mockClient = new MockDataClient(restClient, webSocketClient);
      mockClient.when('tests', {}, [{}, {}, {}]);
      const collection = mockClient.get<TestDataClass>(
        'tests', mockClient.open(), new TestDescriptor(), {}, false);

      await flushPromisesAndTimers();
      expect(collection.array.map(e => e.toObject())).toEqual([
        {testid: 1, testdata: undefined},
        {testid: 2, testdata: undefined},
        {testid: 3, testdata: undefined},
      ]);
    })
  );
});
