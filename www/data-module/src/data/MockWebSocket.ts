/*
  This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0. If a copy of the
  MPL was not distributed with this file, You can obtain one at https://mozilla.org/MPL/2.0/.

  Copyright Buildbot Team Members
*/

export class MockWebSocket implements WebSocket {
  binaryType: BinaryType = 'arraybuffer';
  readonly bufferedAmount: number = 0;
  readonly extensions: string = '';
  onclose: ((this: WebSocket, ev: CloseEvent) => any) | null = null;
  onerror: ((this: WebSocket, ev: Event) => any) | null = null;
  onmessage: ((this: WebSocket, ev: MessageEvent) => any) | null = null;
  onopen: ((this: WebSocket, ev: Event) => any) | null = null;
  readonly protocol: string = '';
  readyState: number = WebSocket.CONNECTING;
  readonly url: string = '';
  close(code?: number, reason?: string): void {}
  readonly CLOSED = WebSocket.CLOSED;
  readonly CLOSING = WebSocket.CLOSING;
  readonly CONNECTING = WebSocket.CONNECTING;
  readonly OPEN = WebSocket.OPEN;

  addEventListener<K extends keyof WebSocketEventMap>(
    type: K, listener: (this: WebSocket, ev: WebSocketEventMap[K]) => any,
    options?: boolean | AddEventListenerOptions) {}
  removeEventListener<K extends keyof WebSocketEventMap>(
    type: K, listener: (this: WebSocket, ev: WebSocketEventMap[K]) => any,
    options?: boolean | EventListenerOptions): void {}
  dispatchEvent(event: Event): boolean { return true; }

  sendQueue: string[] = [];
  parsedSendQueue: any[] = [];

  send(message: string) {
    this.sendQueue.push(message);
    this.parsedSendQueue.push(JSON.parse(message) ?? '');
  }

  clearSendQueue() {
    this.sendQueue = [];
    this.parsedSendQueue = [];
  }

  respond(message: string) {
    if (this.onmessage !== null) {
      this.onmessage(new MessageEvent('', {data: message}));
    }
  }
}
