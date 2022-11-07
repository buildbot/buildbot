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
  readonly CLOSED: number = WebSocket.CLOSED;
  readonly CLOSING: number = WebSocket.CLOSING;
  readonly CONNECTING: number = WebSocket.CONNECTING;
  readonly OPEN: number = WebSocket.OPEN;

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