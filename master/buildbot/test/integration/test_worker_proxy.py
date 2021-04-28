# This file is part of Buildbot.  Buildbot is free software: you can
# redistribute it and/or modify it under the terms of the GNU General Public
# License as published by the Free Software Foundation, version 2.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more
# details.
#
# You should have received a copy of the GNU General Public License along with
# this program; if not, write to the Free Software Foundation, Inc., 51
# Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#
# Copyright Buildbot Team Members

import asyncio
import multiprocessing
import signal
import socket

from twisted.internet import defer

from buildbot.test.util.integration import RunMasterBase

from .interop.test_commandmixin import CommandMixinMasterPB
from .interop.test_compositestepmixin import CompositeStepMixinMasterPb
from .interop.test_integration_secrets import SecretsConfigPB
from .interop.test_interruptcommand import InterruptCommandPb
from .interop.test_setpropertyfromcommand import SetPropertyFromCommandPB
from .interop.test_transfer import TransferStepsMasterPb
from .interop.test_worker_reconnect import WorkerReconnect

# This integration test puts HTTP proxy in between the master and worker.

import os
CURRENT = os.path.dirname(os.path.abspath(__file__))


async def handle_client(local_reader, local_writer):

    async def pipe(reader, writer):
        try:
            while not reader.at_eof():
                writer.write(await reader.read(2048))
        except ConnectionResetError:
            pass
        finally:
            writer.close()

    try:
        request = await local_reader.read(2048)
        lines = request.split(b"\r\n")
        if not lines[0].startswith(b"CONNECT "):
            with open(os.path.join(CURRENT, "stdout.txt"), "a") as outfile:
                outfile.write(f"bad request {request.decode()}\n")
            local_writer.write(b"HTTP/1.1 407 Only CONNECT allowed\r\n\r\n")
            return
        host, port = lines[0].split(b" ")[1].split(b":")
        try:
            remote_reader, remote_writer = await asyncio.open_connection(
                host.decode(), int(port)
            )
        except socket.gaierror:
            with open(os.path.join(CURRENT, "stdout.txt"), "a") as outfile:
                outfile.write(f"failed to relay to {host} {port}\n")
            local_writer.write(b"HTTP/1.1 404 Not Found\r\n\r\n")
            return

        with open(os.path.join(CURRENT, "stdout.txt"), "a") as outfile:
            outfile.write(f"relaying to {host} {port}\n")
        local_writer.write(b"HTTP/1.1 200 Connection established\r\n\r\n")
        pipe1 = pipe(local_reader, remote_writer)
        pipe2 = pipe(remote_reader, local_writer)
        await asyncio.gather(pipe1, pipe2)

    finally:
        local_writer.close()


def run_proxy():
    with open(os.path.join(CURRENT, "stdout.txt"), "a") as outfile:
        outfile.write("run_proxy\n")

    try:
        loop = asyncio.get_event_loop()
        coro = asyncio.start_server(handle_client, "127.0.0.1", 10080)
        server = loop.run_until_complete(coro)

        def signal_handler(sig, trace):
            raise KeyboardInterrupt

        signal.signal(signal.SIGTERM, signal_handler)

        with open(os.path.join(CURRENT, "stdout.txt"), "a") as outfile:
            outfile.write("Serving on {}\n".format(server.sockets[0].getsockname()))
        try:
            with open(os.path.join(CURRENT, "stdout.txt"), "a") as outfile:
                outfile.write("Running forever\n")
            loop.run_forever()
        except KeyboardInterrupt:
            with open(os.path.join(CURRENT, "stdout.txt"), "a") as outfile:
                outfile.write("End\n")
            pass

        server.close()
        loop.run_until_complete(server.wait_closed())
        loop.close()

    except BaseException as e:
        with open(os.path.join(CURRENT, "stdout.txt"), "a") as outfile:
            outfile.write(f"Exception Raised: {str(e)}\n")
            import traceback
            traceback.print_exc(file=outfile)


class RunMasterBehindProxy(RunMasterBase):
    # we need slightly longer timeout for proxy related tests
    timeout = 30

    def setUp(self):
        with open(os.path.join(CURRENT, "stdout.txt"), "w") as outfile:
            outfile.write("setUp\n")
        self.proxy_process = multiprocessing.Process(target=run_proxy)
        self.proxy_process.start()
        with open(os.path.join(CURRENT, "stdout.txt"), "a") as outfile:
            outfile.write(f"X {self.proxy_process.exitcode}\n")
            outfile.write(f"Y {self.proxy_process.is_alive()}\n")

    def tearDown(self):
        with open(os.path.join(CURRENT, "stdout.txt"), "a") as outfile:
            outfile.write("tearDown\n")
        self.proxy_process.terminate()
        self.proxy_process.join()
        print("---- stdout ----")
        with open(os.path.join(CURRENT, "stdout.txt")) as file:
            print(file.read())
        print("---- ------ ----")

    @defer.inlineCallbacks
    def setupConfig(self, config_dict, startWorker=True):
        proxy_connection_string = "tcp:127.0.0.1:10080"
        yield RunMasterBase.setupConfig(self, config_dict, startWorker,
                                        proxy_connection_string=proxy_connection_string)


# Use interoperability test cases to test the HTTP proxy tunneling.

class ProxyCommandMixinMasterPB(RunMasterBehindProxy, CommandMixinMasterPB):
    pass


class ProxyCompositeStepMixinMasterPb(RunMasterBehindProxy, CompositeStepMixinMasterPb):
    pass


class ProxyInterruptCommandPb(RunMasterBehindProxy, InterruptCommandPb):
    pass


class ProxySecretsConfigPB(RunMasterBehindProxy, SecretsConfigPB):
    pass


class ProxySetPropertyFromCommandPB(RunMasterBehindProxy, SetPropertyFromCommandPB):
    pass


class ProxyTransferStepsMasterPb(RunMasterBehindProxy, TransferStepsMasterPb):
    pass


class ProxyWorkerReconnect(RunMasterBehindProxy, WorkerReconnect):
    pass
