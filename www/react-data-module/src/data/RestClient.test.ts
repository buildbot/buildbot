/*
  This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0. If a copy of the
  MPL was not distributed with this file, You can obtain one at https://mozilla.org/MPL/2.0/.

  Copyright Buildbot Team Members
*/

import axios from 'axios';
import MockAdapter from "axios-mock-adapter";
import {RestClient} from "./RestClient";

describe('Rest service', () => {
  let mock : MockAdapter;
  const rootUrl = 'http://test.example.com/api/';

  beforeAll(() => {
    mock = new MockAdapter(axios);
  });

  afterEach(() => {
    mock.reset();
  });

  it('should make an ajax GET call to /api/endpoint', async () => {
    const client = new RestClient(rootUrl);
    const response = {a: 'A'};
    mock.onGet(rootUrl + 'endpoint').reply(200, response);

    const gotResponse = await client.get('endpoint');

    expect(gotResponse).toEqual(response);
  });

  it('should make an ajax GET call to /api/endpoint with parameters', async () => {
    const client = new RestClient(rootUrl);
    const response = {a: 'A'};
    mock.onGet(rootUrl + 'endpoint?key=value').reply(200, response);

    const gotResponse = await client.get('endpoint?key=value');

    expect(gotResponse).toEqual(response);
  });

  it('should reject the promise on error', () => {
    const client = new RestClient(rootUrl);
    const error = 'Internal server error';
    mock.onGet(rootUrl + 'endpoint').reply(500, error);

    expect(client.get('endpoint')).rejects.toEqual(new Error('Request failed with status code 500'));
  });

  it('should make an ajax POST call to /api/endpoint', async () => {
    const client = new RestClient(rootUrl);
    const response = {a: 'A'};
    mock.onPost(rootUrl + 'endpoint').reply(200, response);

    const gotResponse = await client.post('endpoint', {b: 'B'});

    expect(gotResponse).toEqual(response);
  });

  it('should still resolve the promise when the response is not valid JSON', async () => {
    const client = new RestClient(rootUrl);
    const response = 'aaa';
    mock.onGet(rootUrl + 'endpoint').reply(200, response);

    const gotResponse = await client.get('endpoint');

    expect(gotResponse).toEqual(response);
  });

  it('should reject the promise when cancelled', async () => {
    const client = new RestClient(rootUrl);
    mock.onGet(rootUrl + 'endpoint').reply(200, {});

    const request = client.get('endpoint');
    request.cancel();

    expect(request).rejects.toBeInstanceOf(Error);
  });
});
