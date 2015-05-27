from os import path
import hashlib
from buildslave.commands import base
from twisted.internet import threads
from twisted.internet import defer

READ_CHUNK_SIZE = 64 * 1024


class _CheckSumException(Exception):
    pass


def _calc_checksum(rootdir, files, algorithm):
    sums = {}

    for file in files:
        # create the hashing object
        try:
            sum = hashlib.new(algorithm)
        except ValueError as ex:
            raise _CheckSumException(str(ex))

        # read files in chunks and feed it to the hashing object
        try:
            with open(path.join(rootdir, file), "r") as fo:
                while True:
                    chunk = fo.read(READ_CHUNK_SIZE)
                    if not chunk:
                        break
                    sum.update(chunk)
        except IOError as ex:
            raise _CheckSumException(str(ex))

        # store checksum in the results dictionary
        sums[file] = sum.hexdigest()

    return sums


class CheckSums(base.Command):
    #
    # Calculate checksum for specified files.
    #
    #
    # Arguments are: 'workdir'     - work directory for the command
    #                'files'       - list of files for which a checksum
    #                                will be calculated
    #                'algorithm'   - optional name of the algorithm to
    #                                to use e.g. 'md5', 'sha1', etc
    #                                if not specified, md5 will be used
    #                                the algorithms accepted are same as
    #                                by python's hashlib.new() function.
    #
    # The checksums are returned in the 'sums' update field. as a
    # dictionary with file name as a key, and the sum as the value.
    #
    DEFAULT_ALGORITHM = "md5"

    header = "checksums"

    @defer.inlineCallbacks
    def start(self):
        assert "files" in self.args
        assert "workdir" in self.args

        rootdir = path.join(self.builder.basedir, self.args["workdir"])
        files = self.args["files"]
        algorithm = self.args.get("algorithm", self.DEFAULT_ALGORITHM)

        try:
            sums = yield threads.deferToThread(_calc_checksum,
                                               rootdir, files, algorithm)

            self.sendStatus({"sums": sums})
            self.sendStatus({"rc": 0})
        except _CheckSumException as ex:
            self.sendStatus(
                {"header": "error calculating checksum: %s" % str(ex)})
            self.sendStatus({"rc": 1})
