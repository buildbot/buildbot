Master-Worker connection with MessagePack over WebSocket protocol

.. note::

    This is experimental protocol.

=================================================================

Messages between master and worker are sent using WebSocket protocol in both directions.
Data to be sent conceptually is a dictionary and is encoded using MessagePack.
One such encoded dictionary corresponds to one WebSocket message.

A message can be either a request or a response.
Request message is sent when one side wants another one to perform an action.
Once the action is performed, the other side sends the response message back.
A response message is mandatory for every request message.

Message key-value pairs
-----------------------

This section describes a general structure of messages.
It applies for both master and worker.

.. _MsgPack_Request_Message:

Request message
~~~~~~~~~~~~~~~

A request message must contain at least these keys: ``seq_number``, ``op``.
Additional key-value pairs may be supplied depending on the request type.

``seq_number``
    Value is an integer.
    ``seq_number`` must be unique for every request message coming from a particular side.
    The purpose of ``seq_number`` value is to link the request message with response message.
    Response message will carry the same ``seq_number`` value as in corresponding request message.

``op``
    Value is a string.
    It must not be ``response``.
    Each side has a predefined set of commands that another side may invoke.
    ``op`` specifies the command to be invoked by requesting side.

.. _MsgPack_Response_Message:

Response message
~~~~~~~~~~~~~~~~

A response message must contain at least these keys: ``seq_number``, ``op``, ``result``.

``seq_number``
    Value is an integer.
    It represents a number which was specified in the corresponding request message.

``op``
    Value is a string, always a ``response``.

``result``
    Value is ``None`` when success.
    Otherwise – message of exception.

``is_exception``
    This key-value pair is optional.
    If request succeeded this key-value pair is absent.
    Otherwise, its value is a boolean ``True`` and the message of exception is specified in the value of ``result``.


Messages from master to worker
------------------------------

print
~~~~~

Request
+++++++

This message requests worker to print a message to its log.

``seq_number``
    Described in section on :ref:`MsgPack_Request_Message` structure.

``op``
    Value is a string ``print``.

``message``
    Value is a string.
    It represents the string to be printed in worker’s log.

Response
++++++++

Worker prints a message from master to its log.

``seq_number``
    Described in section  on :ref:`MsgPack_Response_Message` structure.

``op``
    Value is a string ``response``.

``result``
    Value is ``None`` if log was printed successfully.
    Otherwise – message of exception.

``is_exception``
    This key-value pair is optional.
    If request succeeded this key-value pair is absent.
    Otherwise, its value is a boolean ``True`` and the message of exception is specified in the value of ``result``.


keep-alive
~~~~~~~~~~

Request
+++++++

Master sends this message to check if the connection is still working.

``seq_number``
    Described in section on :ref:`MsgPack_Request_Message` structure.

``op``
    Value is a string ``keepalive``.

Response
++++++++

Response indicates that connection is still working.

``seq_number``
    Described in section  on :ref:`MsgPack_Response_Message` structure.

``op``
    Value is a string ``response``.

``result``
    Value is ``None``.

get_worker_info
~~~~~~~~~~~~~~~

Request
+++++++

This message requests worker to collect and send the information about itself back to the master.
Only ``op`` and ``seq_number`` values are sent, because worker does not need any additional arguments for this action.

``op``
    Value is a string ``get_worker_info``.

``seq_number``
    Described in section on :ref:`MsgPack_Request_Message` structure.

Response
++++++++

``op``
    Value is a string ``response``.

``seq_number``
    Described in section  on :ref:`MsgPack_Response_Message` structure.

``result``
    Value is a dictionary that contains data about worker.
    Otherwise – message of exception.

``is_exception``
    This key-value pair is optional.
    If request succeeded this key-value pair is absent.
    Otherwise, its value is a boolean ``True`` and the message of exception is specified in the value of ``result``.

Key-value pairs in ``result`` dictionary represent:

``environ``
    Value is a dict.
    It represents environment variables of the worker.

``system``
    Value is a string.
    It represents a name of the operating system dependent module imported.

``basedir``
    Value is a string.
    It represents a path to build directory.

``numcpus``
    Value is an integer.
    It represents a number of CPUs in the system.
    If CPUs number for the worker is not detected, number 1 is set.

``version``
    Value is a string.
    It represents worker version.

``worker_commands``
    Value is a dictionary.
    Keys of this dictionary represent the commands that worker is able to perform.
    Values represent the command version.

Additionally, files in Worker 'basedir/info' directory are read as key-value pairs.
Key is a name of a file and value is the content of a file.
As a convention, there are files named 'admin' and 'host':

``admin``
    Value is a string.
    It specifies information about administrator responsible for this worker.

``host``
    Value is a string.
    It specifies the name of the host.

.. _MsgPack_Request_set_builder_list:

set_builder_list
~~~~~~~~~~~~~~~~

For each master’s (builder, builddir) pair worker creates a corresponding directory.
Directories which exist on the worker and are no longer needed by master, maybe deleted.

Request
+++++++

This message sets builders on which commands may be run.

``seq_number``
    Described in section :ref:`MsgPack_Request_Message` structure.

``op``
    Value is a string ``set_builder_list``.

``builders``
    Value is a list of two-item lists.
    It represents wanted builders names.
    Each tuple contains a builder name and its directory.
    Builds will be run in a directory, whose path is a concatenation of worker base directory (which comes from Worker's configuration file) and the directory received from the master.
    If the directory received from the master is an absolute path, it is used instead for running the builds.

    This directory is called builder directory in the rest of documentation.

Response
++++++++

``seq_number``
    Described in section :ref:`MsgPack_Response_Message` structure.

``op``
    Value is a string ``response``.

``result``
    Value is a list which represents names of builders.
    Otherwise – message of exception.

``is_exception``
    This key-value pair is optional.
    If request succeeded this key-value pair is absent.
    Otherwise, its value is a boolean ``True`` and the message of exception is specified in the value of ``result``.

start_command
~~~~~~~~~~~~~

Request
+++++++

This message requests worker to start a specific command.
Master does not have to wait for completion of previous commands before starting a new one, so many different commands may be running in worker simultaneously.

Each start command request message has a unique ``command_id`` value.

Worker may be sending request ``update`` messages to master which update master about status of started command.
When worker sends a request ``update`` message about command, the message takes a ``command_id`` value from corresponding start command request message.
Accordingly master can match update messages to the commands they correspond to.
When command execution in worker is completed, worker sends a request ``complete`` message to master with the ``command_id`` value of the completed command.
It allows master to track which command exactly was completed.

``op``
    Value is a string ``start_command``.

``seq_number``
    Described in section :ref:`MsgPack_Request_Message` structure.

``builder_name``
    Value is a string.
    It represents the builder, which should start a command.

``command_id``
    Value is a string value that is unique per worker connection.

``command_name``
    Value is a string.
    It represents a name of the command to be called.

``args``
    Value is a dictionary.
    It represents arguments needed to run the command and any additional information about a command.

    Arguments of all different commands are explained in section :ref:`MsgPack_Request_Types_Message`.


Response
++++++++

``op``
    Value is a string ``response``.

``seq_number``
    Described in section :ref:`MsgPack_Response_Message` structure.

``result``
    Value is ``None`` when success.
    Otherwise – message of exception.

``is_exception``
    This key-value pair is optional.
    If request succeeded this key-value pair is absent.
    Otherwise, its value is a boolean ``True`` and the message of exception is specified in the value of ``result``.


interrupt_command
~~~~~~~~~~~~~~~~~

Request
+++++++

This message requests worker to halt the specified command.

``seq_number``
    Described in section :ref:`MsgPack_Request_Message`

``op``
    Value is a string ``interrupt_command``.

``builder_name``
    Value is a string.
    It represents a name of a builder which should interrupt its command.

``command_id``
    Value is a string which identifies the command to interrupt.

``why``
    Value is a string.
    It represents the reason of interrupting command.

Response
++++++++

During this command worker may also send back additional update messages to the master.
Update messages are explained in section :ref:`MsgPack_Update_Message`.

``op``
    Value is a string ``response``.

``seq_number``
    Described in section :ref:`MsgPack_Response_Message`

``result``
    Value is ``None`` if success.
    Otherwise – message of exception.

``is_exception``
    This key-value pair is optional.
    If request succeeded this key-value pair is absent.
    Otherwise, its value is a boolean ``True`` and the message of exception is specified in the value of ``result``.

shutdown
~~~~~~~~

Request
+++++++

This message requests worker to shutdown itself.
Action does not require arguments,  so only ``op`` and ``seq_number`` values are sent.

``seq_number``
    Described in section :ref:`MsgPack_Request_Message`

``op``
    The value is a string ``shutdown``.

Response
++++++++

Worker returns ``result``: ``None`` without waiting for completion of shutdown.

``op``
    Value is a string ``response``.

``seq_number``
    Described in section :ref:`MsgPack_Response_Message`.

``result``
    Value is ``None`` if success.
    Otherwise – message of exception.

``is_exception``
    This key-value pair is optional.
    If request succeeded this key-value pair is absent.
    Otherwise, its value is a boolean ``True`` and the message of exception is specified in the value of ``result``.

Messages from worker to master
------------------------------

auth
~~~~

Request
+++++++

The authentication message requests master to authenticate username and password given by the worker.
This message must be the first message sent by worker.

``seq_number``
    Described in section :ref:`MsgPack_Request_Message`.

``op``
    Value is a string ``auth``.

``username``
    Value is a string.
    It represents a username of a connecting worker.

``password``
    Value is a string.
    It represents a password of a connecting worker.


Response
++++++++

Master returns ``result``: ``True`` if authentication was successful and worker has logged to master.

``op``
    Value is a string ``response``.

``seq_number``
    Described in section :ref:`MsgPack_Response_Message`.

``result``
    Value is ``True`` when authentication succeeded, ``False`` if authentication failed.
    If request itself failed due to reason not related to authentication, value contains the message of exception.

``is_exception``
    This key-value pair is optional.
    If request succeeded this key-value pair is absent.
    Otherwise, its value is a boolean ``True`` and the message of exception is specified in the value of ``result``.

.. _MsgPack_Update_Message:

update
~~~~~~

From the start of a command till its completion, worker may be updating master about the processes of commands it requested to start.
These updates are sent in an ``update`` messages.

Request
+++++++

``seq_number``
    Described in section :ref:`MsgPack_Request_Message`.

``op``
    Value is a string ``update``.

``args``
    Value is a list of lists.
    Inner list contains a dictionary and an integer.
    Keys and values of the dictionary are further explained in section :ref:`MsgPack_Keys_And_Values_Message`.

``command_id``
    Value is a string which identifies command the update refers to.

Response
++++++++

``op``
    Value is a string ``response``.

``seq_number``
    Described in section :ref:`MsgPack_Response_Message`.

``result``
    Value is ``None`` when master successfully acknowledges the update.
    Otherwise – message of exception.

``is_exception``
    This key-value pair is optional.
    If request succeeded this key-value pair is absent.
    Otherwise, its value is a boolean ``True`` and the message of exception is specified in the value of ``result``.

update_upload_file_write
~~~~~~~~~~~~~~~~~~~~~~~~

Request
+++++++

``op``
    Value is a string ``update_upload_file_write``.

``args``
    Contents of the chunk from the file that worker read.

``command_id``
    Value is a string which identifies command the update refers to.

Response
++++++++

``op``
    Value is a string ``response``.

``seq_number``
    Described in section :ref:`MsgPack_Response_Message`.

``result``
    Value is ``None`` when master successfully acknowledges the update.
    Otherwise – message of exception.

``is_exception``
    This key-value pair is optional.
    If request succeeded this key-value pair is absent.
    Otherwise, its value is a boolean ``True`` and the message of exception is specified in the value of ``result``.

update_upload_file_close
~~~~~~~~~~~~~~~~~~~~~~~~

By this command worker states that no more data will be transferred.

Request
+++++++

``op``
    Value is a string ``update_upload_file_close``.

``command_id``
    Value is a string which identifies command the update refers to.

Response
++++++++

``op``
    Value is a string ``response``.

``seq_number``
    Described in section :ref:`MsgPack_Response_Message`.

``result``
    Value is ``None`` when master successfully acknowledges the update.
    Otherwise – message of exception.

``is_exception``
    This key-value pair is optional.
    If request succeeded this key-value pair is absent.
    Otherwise, its value is a boolean ``True`` and the message of exception is specified in the value of ``result``.

update_upload_file_utime
~~~~~~~~~~~~~~~~~~~~~~~~

Request
+++++++

``op``
    Value is a string ``update_upload_file_utime``.

``access_time``
    Value is a floating point number.
    It is a number of seconds that passed from the start of the Unix epoch (January 1, 1970, 00:00:00 (UTC)) and last access of path.

``modified_time``
    Value is a floating point number.
    It is a number of seconds that passed from the start of the Unix epoch (January 1, 1970, 00:00:00 (UTC)) and last modification of path.


``command_id``
    Value is a string which identifies command the update refers to.

Response
++++++++

``op``
    Value is a string ``response``.

``seq_number``
    Described in section :ref:`MsgPack_Response_Message`.

``result``
    Value is ``None`` when master successfully acknowledges the update.
    Otherwise – message of exception.

``is_exception``
    This key-value pair is optional.
    If request succeeded this key-value pair is absent.
    Otherwise, its value is a boolean ``True`` and the message of exception is specified in the value of ``result``.

update_read_file
~~~~~~~~~~~~~~~~

Request
+++++++

``op``
    Value is a string ``update_read_file``.

``length``
    Maximum number of bytes of data to read.

``command_id``
    Value is a string which identifies command the update refers to.

Response
++++++++

``op``
    Value is a string ``response``.

``seq_number``
    Described in section :ref:`MsgPack_Response_Message`.

``result``
    Value is data of length ``length`` that master read from its file.
    Otherwise – message of exception.

``is_exception``
    This key-value pair is optional.
    If request succeeded this key-value pair is absent.
    Otherwise, its value is a boolean ``True`` and the message of exception is specified in the value of ``result``.

update_read_file_close
~~~~~~~~~~~~~~~~~~~~~~

By this command worker states that no more data will be transferred.

Request
+++++++

``op``
    Value is a string ``update_read_file_close``.

``command_id``
    Value is a string which identifies command the update refers to.

Response
++++++++

``op``
    Value is a string ``response``.

``seq_number``
    Described in section :ref:`MsgPack_Response_Message`.

``result``
    Value is ``None`` when master successfully acknowledges the update.
    Otherwise – message of exception.

``is_exception``
    This key-value pair is optional.
    If request succeeded this key-value pair is absent.
    Otherwise, its value is a boolean ``True`` and the message of exception is specified in the value of ``result``.

update_upload_directory_write
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Request
+++++++

``op``
    Value is a string ``update_upload_directory_write``.

``args``
    Contents of the chunk from the directory that worker read.

``command_id``
    Value is a string which identifies command the update refers to.

Response
++++++++

``op``
    Value is a string ``response``.

``seq_number``
    Described in section :ref:`MsgPack_Response_Message`.

``result``
    Value is ``None`` when master successfully acknowledges the update.
    Otherwise – message of exception.

``is_exception``
    This key-value pair is optional.
    If request succeeded this key-value pair is absent.
    Otherwise, its value is a boolean ``True`` and the message of exception is specified in the value of ``result``.

update_upload_directory_unpack
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

By this command worker states that no more data will be transferred.

Request
+++++++

``op``
    Value is a string ``update_upload_directory_unpack``.

``command_id``
    Value is a string which identifies command the update refers to.

Response
++++++++

``op``
    Value is a string ``response``.

``seq_number``
    Described in section :ref:`MsgPack_Response_Message`.

``result``
    Value is ``None`` when master successfully acknowledges the update.
    Otherwise – message of exception.

``is_exception``
    This key-value pair is optional.
    If request succeeded this key-value pair is absent.
    Otherwise, its value is a boolean ``True`` and the message of exception is specified in the value of ``result``.

complete
~~~~~~~~

Notifies master that the remote command has finished.

Request
+++++++

``seq_number``
    Described in section :ref:`MsgPack_Request_Message`

``op``
    Value is a string ``complete``.

``args``
    ``None`` if a command succeeded.
    A message of error as a string if command failed.

``command_id``
    Value is a string which identifies command to complete.

Response
++++++++

``op``
    Value is a string ``response``.

``seq_number``
    Described in section :ref:`MsgPack_Response_Message`.

``result``
    Value is ``None`` when master successfully acknowledges the completion.
    Otherwise – message of exception.

``is_exception``
    This key-value pair is optional.
    If request succeeded this key-value pair is absent.
    Otherwise, its value is a boolean ``True`` and the message of exception is specified in the value of ``result``.

.. _MsgPack_Request_Types_Message:


``start_command`` request types
-------------------------------

Request causes worker to start performing an action.
There are multiple types of the request each supporting a particular type of worker action.
The basic structure of request is the same as explained in section :ref:`MsgPack_Request_Message`.

Values of ``command_name`` and ``args`` keys depend on the specific command within the request message dictionary.
``command_name`` is a string which defines command type.
``args`` is a dictionary which defines the arguments and other variables worker needs to perform the command successfully.
Worker starts a program specified in the key ``command_name`` and sends updates to the master about ongoing command.

Command names and their arguments dictionary key-value pairs are explained below.

Command_name: ``shell``
~~~~~~~~~~~~~~~~~~~~~~~

Runs a ``shell`` command on the worker.

``workdir``
    Value is a string.
    This value is joined with the builder directory string (see :ref:`MsgPack_Request_set_builder_list`) to form the path string.
    If ``workdir`` is an absolute path, it overrides the builder directory.
    The resulting path represents the worker directory to run the command in.

``env``
    Value is a dictionary and is optional.
    It contains key-value pairs that specify environment variables for the environment in which a new command is started.

    If the value is of type list, its elements are concatenated to a single string using a platform specific path separator between the elements.

    If this dictionary contains "PYTHONPATH" key, path separator and "$PYTHONPATH" is appended to that value.

    Resulting environment dictionary sent to the command is created following these rules:

    1) If ``env`` has value for specific key and it is ``None``, resulting dictionary does not have this key.

    2) If ``env`` has value for specific key and it is not ``None``, resulting dictionary contains this value with substitutions applied.

    Any matches of a pattern ``${name}`` in this value, where name is any number of alphanumeric characters, are substituted with the value of the same key from worker environment.

    3) If a specific key from worker environment is not present in ``env``, resulting dictionary contains that key-value pair from worker environment.

``want_stdout``
    Value is a bool and is optional.
    If value is not specified, the default is ``True``.
    If value is ``True``, worker sends ``update`` log messages to master from the process ``stdout`` output.

``want_stderr``
    Value is a bool and is optional.
    If value is not specified, the default is True.
    If value is ``True``, worker sends ``update`` log messages to the master from the process ``stderr`` output.

``logfiles``
    Value is a dictionary and is optional.
    If the value is not specified, the default is an empty dictionary.

    This dictionary specifies logfiles other than stdio.

    Keys are the logfile names.

    Worker reads this logfile and sends the data with the ``update`` message, where logfile name as a key identifies data of different logfiles.

    Value is a dictionary. It contains the following keys:

    ``filename``
        Value is a string. It represents the filename of the logfile, relative to worker directory where the command is run.

    ``follow``
        Value is a boolean.
        If ``True`` - only follow the file from its current end-of-file, rather than starting from the beginning.
        The default is ``False``.

``timeout``
    Value is an integer and is optional.
    If value is not specified, the default is ``None``.
    It represents, how many seconds a worker should wait before killing a process after it gives no output.

``maxTime``
    Value is an integer and is optional.
    If value is not specified, the default is ``None``.
    It represents, how many seconds a worker should wait before killing a process.
    Even if command is still running and giving the output, ``maxTime`` variable sets the maximum time the command is allowed to be performing.
    If ``maxTime`` is set to ``None``, command runs for as long as it needs unless ``timeout`` specifies otherwise.

``sigtermTime``
    Value is an integer and is optional.
    If value is not specified, the default is ``None``.
    It specifies how to abort the process.
    If ``sigtermTime`` is not ``None`` when aborting the process, worker sends a signal SIGTERM.
    After sending this signal, worker waits for ``sigtermTime`` seconds of time and if the process is still alive, sends the signal SIGKILL.
    If ``sigtermTime`` is ``None``, worker does not wait and sends signal SIGKILL to the process immediately.

``usePTY``
    Value is a bool and is optional.
    If value is not specified, the default is ``False``.
    ``True`` to use a PTY, ``False`` to not use a PTY.

``logEnviron``
    Value is a bool and is optional.
    If value is not specified, the default is ``True``.
    If ``True``, worker sends to master an ``update`` message with process environment key-value pairs at the beginning of a process.

``initial_stdin``
    Value is a string or ``None``.
    If not ``None``, the value is sent to the process as an initial stdin after process is started.
    If value is ``None``, no initial stdin is sent.

``command``
    Value is a list of strings or a string.
    It represents the name of a program to be started and its arguments.
    If this is a string, it will be invoked via ``/bin/sh`` shell by calling it as ``/bin/sh -c <command>``.
    Otherwise, it must be a list, which will be executed directly.


    If command succeeded, worker sends ``rc`` value 0 as an ``update`` message ``args`` key-value pair.
    It can also send many ``update`` messages with key ``header``, ``stdout`` or ```stderr` to inform about command execution.
    If command failed, it sends ``rc`` value with the error number.

    The basic structure of worker ``update`` message is explained in section :ref:`MsgPack_Keys_And_Values_Message`.


Command_name: ``upload_file``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Worker reads the contents of its file and sends them in chunks to write into the file on masters’s side.

``workdir``
    Value is a string.
    It represents a base directory for the filename, relative to the builder's basedir.

``workersrc``
    Value is a string.
    It represents a path to the worker-side file to read from, relative to the workdir.

``maxsize``
    Value is an integer.
    Maximum number of bytes to transfer from the worker.
    The operation will fail if the file exceeds this size.
    Worker will send messages with data to master until it notices it exceeded ``maxsize``.

``blocksize``
    Value is an integer.
    Maximum size for each data block to be sent to master.

``keepstamp``
    Value is a bool.
    It represents whether to preserve "file modified" and "accessed" times.
    ``True`` is for preserving.

    Workers sends data to master with one or more ``update_upload_file_write`` messages.
    After reading the file is over, worker sends ``update_upload_file_close`` message.
    If ``keepstamp`` was ``True``, workers sends ``update_upload_file_utime`` message.
    If command succeeded, worker sends ``rc`` value 0 as an ``update`` message ``args`` key-value pair.
    It can also send ``update`` messages with key ``header`` or ``stderr`` to inform about command execution.

    If command failed, worker sends ``update_upload_file_close`` message and the ``update`` message with dictionary ``args`` key ``rc`` with the error number.

    The basic structure of worker ``update`` message is explained in section :ref:`MsgPack_Keys_And_Values_Message`.


Command_name: ``upload_directory``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Similar to ``upload_file``.
This command will upload an entire directory to the master, in the form of a tarball.

``workdir``
    Value is a string.
    It represents a base directory for the filename, relative to the builder's basedir.

``workersource``
    Value is a string.
    It represents a path to the worker-side directory to read from, relative to the workdir.

``maxsize``
    Value is an integer.
    Maximum number of bytes to transfer from the worker.
    The operation will fail if the tarball file exceeds this size.
    Worker will send messages with data to master until it notices it exceeded ``maxsize``.

``blocksize``
    Value is an integer.
    Maximum size for each data block to be sent to master.

``compress``
    Compression algorithm to use – one of ``None``, 'bz2', or 'gz'.

    Worker sends data to the master with one or more ``update_upload_directory_write`` messages.
    After reading the directory, worker sends ``update_upload_directory_unpack`` with no arguments to extract the tarball and ``rc`` value 0 as an ``update`` message ``args`` key-value pair if the command succeeded.

    Otherwise, worker sends ``update`` message with dictionary ``args`` key ``header`` with information about the error that occurred and another ``update`` message with dictionary ``args`` key ``rc`` with the error number.

The basic structure of worker ``update`` message is explained in section :ref:`MsgPack_Keys_And_Values_Message`.


Command_name: ``download_file``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Downloads a file from master to worker.

``workdir``
    Value is a string.
    It represents a base directory for the filename, relative to the builder's basedir.

``workerdest``
    Value is a string.
    It represents a path to the worker-side file to write to, relative to the workdir.

``maxsize``
    Value is an integer.
    Maximum number of bytes to transfer from the master.
    The operation will fail if the file exceeds this size.
    Worker will request data from master until it notices it exceeded ``maxsize``.

``blocksize``
    Value is an integer.
    It represents maximum size for each data block to be sent from master to worker.

``mode``
    Value is ``None`` or an integer which represents an access mode for the new file.

    256 - owner has read permission.

    128 - owner has write permission.

    64 - owner has execute permission.

    32 - group has read permission.

    16 - group has write permission.

    8 - group has execute permission.

    4 - others have read permission.

    2 - others have write permission.

    1 - others have execute permission.

    If ``None``, file has default permissions.

    If command succeeded, worker will send ``rc`` value 0 as an ``update`` message ``args`` key-value pair.

    Otherwise, worker sends ``update`` message with dictionary ``args`` key ``header`` with information about the error that occurred and another ``update`` message with dictionary ``args`` key ``rc`` with the error number.

    The basic structure of worker ``update`` message is explained in section :ref:`MsgPack_Keys_And_Values_Message`.


Command_name: ``listdir``
~~~~~~~~~~~~~~~~~~~~~~~~~

This command reads the directory and returns the list with directory contents.

``dir``
    Value is a string.
    Specifies the directory relative to the builder’s basedir.

    Worker creates the path to list by joining base directory and the given value.

    If command succeeded, the list containing the names of the entries in the directory given by that path is sent via ``update`` message in ``args`` key ``files``.
    Worker will also send ``rc`` value 0 as an ``update`` message ``args`` key-value pair.
    If command failed, worker sends ``update`` message with dictionary ``args`` key ``header`` with information about the error that occurred and another ``update`` message with dictionary ``args`` key ``rc`` with the error number.

    The basic structure of worker ``update`` message is explained in section :ref:`MsgPack_Keys_And_Values_Message`.

Command_name: ``mkdir``
~~~~~~~~~~~~~~~~~~~~~~~

This command will create a directory on the worker.
It will also create any intervening directories required.

``dir``
    Value is a string.
    Specifies the directory relative to the builder’s basedir.

    Worker creates the path to directory by joining the base directory and given value.

    If command succeeded, worker will send ``rc`` value 0 as an ``update`` message ``args`` key-value pair.

    Otherwise, worker sends ``update`` message with dictionary ``args`` key ``header`` with information about the error that occurred and another ``update`` message with dictionary ``args`` key ``rc`` with the error number.

    The basic structure of worker ``update`` message is explained in section :ref:`MsgPack_Keys_And_Values_Message`.


Command_name ``rmdir``
~~~~~~~~~~~~~~~~~~~~~~

This command will remove a directory or file on the worker.

``dir``
    Value is a string or a list of strings.
    It represents a name of a directory or directories to be removed.

``logEnviron``
    Value is a bool and is optional.
    If value is not specified, the default is ``True``.
    If ``True``, worker sends to master an ``update`` message with process environment key-value pairs at the beginning of a process.

``timeout``
    Value is an integer and is optional.
    If value is not specified, the default is 120s.
    It represents how many seconds a worker should wait before killing a process when it gives no output.

``maxTime``
    Value is an integer and is optional.
    If value is not specified, the default is ``None``.
    It represents, how many seconds a worker should wait before killing a process.
    Even if command is still running and giving the output, ``maxTime`` variable sets the maximum time the command is allowed to be performing.
    If ``maxTime`` is set to ``None``, command runs for as long as it needs unless ``timeout`` specifies otherwise.

    If command succeeded, worker sends ``rc`` value 0 as an ``update`` message ``args`` key-value pair.
    It can also send many ``update`` messages with key ``header``, ``stdout`` or ``stderr`` to inform about command execution.
    If command failed, worker changes the permissions of a directory and tries the removal once again.
    If that does not help, worker sends ``rc`` value with the error number.

    The basic structure of worker ``update`` message is explained in section :ref:`MsgPack_Keys_And_Values_Message`.


Command_name: ``cpdir``
~~~~~~~~~~~~~~~~~~~~~~~

This command copies a directory from one place in the worker to another.

``fromdir``
    Value is a string.
    Source directory for the copy operation, relative to the builder’s basedir.

``todir``
    Value is a string.
    Destination directory for the copy operation, relative to the builder’s basedir.

``logEnviron``
    Value is a bool.
    If ``True``, worker sends to master an ``update`` message with process environment key-value pairs at the beginning of a process.

``timeout``
    Value is an integer.
    If value is not specified, the default is 120s.
    It represents, how many seconds a worker should wait before killing a process if it gives no output.

``maxTime``
    Value is an integer and is optional.
    If value is not specified, the default is ``None``.
    It represents, how many seconds a worker should wait before killing a process.
    Even if command is still running and giving the output, ``maxTime`` variable sets the maximum time the command is allowed to be performing.
    If ``maxTime`` is set to ``None``, command runs for as long as it needs unless ``timeout`` specifies otherwise.

    If command succeeded, worker sends ``rc`` value 0 as an ``update`` message ``args`` key-value pair.
    It can also send many ``update`` messages with key ``header``, ``stdout`` or ```stderr` to inform about command execution.
    If command failed, it sends ``rc`` value with the error number.

    The basic structure of worker ``update`` message is explained in section :ref:`MsgPack_Keys_And_Values_Message`.


Command_name: ``stat``
~~~~~~~~~~~~~~~~~~~~~~

This command returns status information about workers file or directory.
Path of that file or directory is constructed by joining the Builder base directory and path in ``file`` value.

``file``
    Value is a string.
    It represents the filename relative to the Builder’s basedir to get the status of.

If command succeeded, status information is sent to the master in an ``update`` message, where ``args`` has a key ``stat`` with a value of a tuple of these 10 elements:

0 - File mode: file type and file mode bits (permissions) in Unix convention.

1 - Platform dependent, but if non-zero, uniquely identifies the file for a specific device.

2 - Unique ID of disc device where this file resides.

3 - Number of hard links.

4 - ID of the file owner.

5 - Group ID of the file owner.

6 - If the file is a regular file or a symbolic link, size of the file in bytes, otherwise unspecified.

Timestamps depend on the platform:

Unix time or the time of Windows creation, expressed in seconds.

7 - time of last access in seconds.

8 - time of last data modification in seconds.

9 - time of last status change in seconds.

    If command succeeded, worker also sends ``rc`` value 0 as an ``update`` message ``args`` key-value pair.

    Otherwise, worker sends ``update`` message with dictionary ``args`` key ``header`` with information about the error that occurred and another ``update`` message with dictionary ``args`` key ``rc`` with the error number.

    The basic structure of worker ``update`` message is explained in section :ref:`MsgPack_Keys_And_Values_Message`.


Command_name: ``glob``
~~~~~~~~~~~~~~~~~~~~~~

    Worker sends to the master a possibly-empty list of path names that match shell-style path specification.

    Path of the file is constructed by joining the Builder base directory and path in ``path`` value.
    Pathname can be absolute or relative with or without shell-style wildcards.

``path``
    Value is a string.
    It represents a shell-style path specification of a pattern.

    If command succeeded, the result is sent to the master in an ``update`` message, where ``args`` has a key ``file`` with the value of that possibly-empty path list.
    Worker also sends ``rc`` value 0 as an ``update`` message ``args`` key-value pair.

    Otherwise, worker sends ``update`` message with dictionary ``args`` key ``header`` with information about the error that occurred and another ``update`` message with dictionary ``args`` key ``rc`` with the error number.

    The basic structure of worker ``update`` message is explained in section :ref:`MsgPack_Keys_And_Values_Message`.


Command_name: ``rmfile``
~~~~~~~~~~~~~~~~~~~~~~~~

This command removes the specified file.

``path``
    Value is a string.
    It represents the file path relative to the builder’s basedir.
    Worker removes (deletes) the file ``path``.

    If command succeeded, worker sends ``rc`` value 0 as an ``update`` message ``args`` key-value pair.

    Otherwise, worker sends ``update`` message with dictionary ``args`` key ``header`` with information about the error that occurred and another ``update`` message with dictionary ``args`` key ``rc`` with the error number.

    The basic structure of worker ``update`` message is explained in section :ref:`MsgPack_Keys_And_Values_Message`.


.. _MsgPack_Keys_And_Values_Message:


Keys and values of ``args`` dictionary value in ``update`` request message
--------------------------------------------------------------------------

Commands may have specific key-value pairs so only common ones are described here.

``stdout``
    Value is a standard output of a process.
    Some of the commands that master requests worker to start, may initiate processes which output a result as a standard output and this result is saved in the value of ``stdout``.

``rc``
    Value is an integer.
    It represents an exit code of a process.
    0 if the process exit was successful.
    Any other number represents a failure.

``header``
    Value is a string.
    It represents additional information about how the command worked.
    For example, information may include the command name and arguments, working directory and environment or various errors or warnings of a process or other information that may be useful for debugging.

``files``
    Value is a list of strings.

    1) If the ``update`` message was a response to master request message ``start_command`` with a key value pair ``command_name`` and ``glob``, then strings in this list represent path names that matched pathname given by the master.

    2) If the ``update`` message was a response to master request message ``start_command`` with a key value pair ``command_name`` and ``listdir``, then strings in this list represent the names of the entries in the directory given by path, which master sent as an argument.

``stderr``
    Value is a standard error of a process.
    Some of the commands that master requests worker to start may initiate processes which can output a result as a standard error and this result is saved in the value of ``stderr``.

``Tuple (“log”, name)``
    Value is a string.
    This message is used to transfer the contents of the file that master requested worker to read.
    This file is identified by the second member in workers tuple.
    The same value is sent by master as the key of dictionary represented by ``logfile`` key within ``args`` dictionary of ``StartCommand`` command.
    The string value of the message is the contents of a file that worker read.

``elapsed``
    Value is an integer.
    It represents how much time has passed between the start of a command and the completion in seconds.
