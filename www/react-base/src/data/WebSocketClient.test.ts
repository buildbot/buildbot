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

import {getWebSocketUrl, WebSocketClient} from "./WebSocketClient";
import {MockWebSocket} from "./MockWebSocket";

describe('Web socket client', () => {
  function createMockClient(): [WebSocketClient, MockWebSocket] {
    const client = new WebSocketClient('url', (_) => new MockWebSocket());
    const socket = client.socket as MockWebSocket;
    return [client, socket];
  }

  function openSocket(socket: MockWebSocket) {
    if (socket.onopen !== null)
      socket.onopen({} as Event);
  }

  it('should send the data, when the WebSocket is open', () => {
    const [client, socket] = createMockClient();

    socket.readyState = WebSocket.CONNECTING;
    // 2 message to be sent
    const msg1 = {a: 1};
    const msg2 = {b: 2};
    const msg3 = {c: 3};
    client.send(msg1);
    client.send(msg2);
    expect(socket.sendQueue.length).toBe(0);
    openSocket(socket);
    expect(socket.sendQueue.length).toBe(2);
    expect(socket.sendQueue).toContain(JSON.stringify(msg1));
    expect(socket.sendQueue).toContain(JSON.stringify(msg2));
    expect(socket.sendQueue).not.toContain(JSON.stringify(msg3));
  });

  it('should add an _id to each message', () => {
    const [client, socket] = createMockClient();

    socket.readyState = WebSocket.OPEN;
    expect(socket.sendQueue.length).toBe(0);
    client.send({});
    expect(socket.sendQueue).toContain(JSON.stringify({'_id': 1}));
  });

  it('should resolve the promise when a response message is received with code 200', () => {
    const [client, socket] = createMockClient();

    socket.readyState = WebSocket.OPEN;
    const msg = {cmd: 'command'};
    const promise = client.send(msg);

    // create a response message with status code 200
    const id = socket.parsedSendQueue[0]._id;
    const response = JSON.stringify({_id: id, code: 200});

    socket.respond(response);
    expect(promise).resolves.toEqual(undefined);
  });

  it('should reject the promise when a response message is received, but the code is not 200', () => {
    const [client, socket] = createMockClient();

    socket.readyState = WebSocket.OPEN;
    const msg = {cmd: 'command'};
    const promise = client.send(msg);

    // send a response message with status code 500
    const id = socket.parsedSendQueue[0]._id;
    socket.respond(JSON.stringify({_id: id, code: 500}));
    expect(promise).rejects.toBeInstanceOf(Error);
  });


  describe('getWebSocketUrl()', () => {

    it('should support url based on the host and port (localhost)', () => {
      const location = {
        protocol: 'http:',
        hostname: 'localhost',
        port: '8080',
        pathname: '/',
      } as Location;
      expect(getWebSocketUrl(location)).toBe('ws://localhost:8080/ws');
    });

    it('should support url based on the host and port', () => {
      const location = {
        protocol: 'http:',
        hostname: 'buildbot.test',
        port: '80',
        pathname: '/',
      } as Location;
      expect(getWebSocketUrl(location)).toBe('ws://buildbot.test/ws');
    });

    it('should support url based on host and port and protocol', () => {
      const location = {
        protocol: 'https:',
        hostname: 'buildbot.test',
        port: '443',
        pathname: '/',
      } as Location;
      expect(getWebSocketUrl(location)).toBe('wss://buildbot.test/ws');
    });

    it('should support url based on host and port and protocol and basedir', () => {
      const location = {
        protocol: 'https:',
        hostname: 'buildbot.test',
        port: '443',
        pathname: '/travis/',
      } as Location;
      expect(getWebSocketUrl(location)).toBe('wss://buildbot.test/travis/ws');
    });
  });
});
