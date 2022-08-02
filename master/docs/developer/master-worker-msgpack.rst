Master-Worker connection with MessagePack over WebSocket protocol
=================================================================

.. note::

    This is experimental protocol.

Messages between master and worker are sent using WebSocket protocol in both directions.
Data to be sent conceptually is a dictionary and is encoded using MessagePack.
One such encoded dictionary corresponds to one WebSocket message.

Authentication happens during opening WebSocket handshake using standard HTTP Basic authentication.
Worker credentials are sent in the value of the HTTP "Authorization" header.
Master checks if the credentials match and if not - the connection is terminated.

A WebSocket message can be either a request or a response.
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

set_worker_settings
~~~~~~~~~~~~~~~~~~~

Request
+++++++

Master sends this message to set worker settings.
The settings must be sent from master before first command.

``seq_number``
    Described in section on :ref:`MsgPack_Request_Message` structure.

``op``
    Value is a string ``set_worker_settings``.

``args``
    Value is a dictionary.
    It represents the settings needed for worker to format command output and buffer messages.
    The following settings are mandatory:

    * "buffer_size" - the maximum size of buffer in bytes to fill before sending an update message.

    * "buffer_timeout" - the maximum time in seconds that data can wait in buffer before update message is sent.

    * "newline_re" - the pattern in output string, which will be replaced with newline symbol.

    * "max_line_length" - the maximum size of command output line in bytes.

Response
++++++++

``seq_number``
    Described in section  on :ref:`MsgPack_Response_Message` structure.

``op``
    Value is a string ``response``.

``result``
    Value is ``None`` if success.
    Otherwise – message of exception.

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
    Value is a list of two-element lists.
    These two elements in sub-lists represent name-value pairs: first element is the name of update and second is its value.
    The names and values are further explained in section :ref:`MsgPack_Keys_And_Values_Message`.

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
    ``workdir`` is an absolute path and overrides the builder directory.
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
    It can also send many other ``update`` messages with keys such as ``header``, ``stdout`` or ``stderr`` to inform about command execution.
    If command failed, it sends ``rc`` value with the error number.

    The basic structure of worker ``update`` message is explained in section :ref:`MsgPack_Keys_And_Values_Message`.


Command_name: ``upload_file``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Worker reads the contents of its file and sends them in chunks to write into the file on masters’s side.

``path``
    Value is a string.
    It specifies the path of the worker file to read from.

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

``path``
    Value is a string.
    It specifies the path of the worker directory to upload.

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

``path``
    Value is a string.
    It specifies the path of the worker file to create.

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

``path``
    Value is a string.
    It specifies the path of a directory to list.

    If command succeeded, the list containing the names of the entries in the directory given by that path is sent via ``update`` message in ``args`` key ``files``.
    Worker will also send ``rc`` value 0 as an ``update`` message ``args`` key-value pair.
    If command failed, worker sends ``update`` message with dictionary ``args`` key ``header`` with information about the error that occurred and another ``update`` message with dictionary ``args`` key ``rc`` with the error number.

    The basic structure of worker ``update`` message is explained in section :ref:`MsgPack_Keys_And_Values_Message`.

Command_name: ``mkdir``
~~~~~~~~~~~~~~~~~~~~~~~

This command will create a directory on the worker.
It will also create any intervening directories required.

``paths``
    Value is a list of strings.
    It specifies absolute paths of directories to create.

    If command succeeded, worker will send ``rc`` value 0 as an ``update`` message ``args`` key-value pair.

    Otherwise, worker sends ``update`` message with dictionary ``args`` key ``header`` with information about the error that occurred and another ``update`` message with dictionary ``args`` key ``rc`` with the error number.

    The basic structure of worker ``update`` message is explained in section :ref:`MsgPack_Keys_And_Values_Message`.


Command_name ``rmdir``
~~~~~~~~~~~~~~~~~~~~~~

This command will remove directories or files on the worker.

``paths``
    Value is a list of strings.
    It specifies absolute paths of directories or files to remove.

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

``from_path``
    Value is a string.
    It specifies the absolute path to the source directory for the copy operation.

``to_path``
    Value is a string.
    It specifies the absolute path to the destination directory for the copy operation.

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

``path``
    Value is a string.
    It specifies the path of a file or directory to get the status of.

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

``path``
    Value is a string.
    It specifies a shell-style path pattern.
    Path pattern can contain shell-style wildcards and must represent an absolute path.

    If command succeeded, the result is sent to the master in an ``update`` message, where ``args`` has a key ``file`` with the value of that possibly-empty path list.
    This path list may contain broken symlinks as in the shell.
    It is not specified whether path list is sorted.

    Worker also sends ``rc`` value 0 as an ``update`` message ``args`` key-value pair.

    Otherwise, worker sends ``update`` message with dictionary ``args`` key ``header`` with information about the error that occurred and another ``update`` message with dictionary ``args`` key ``rc`` with the error number.

    The basic structure of worker ``update`` message is explained in section :ref:`MsgPack_Keys_And_Values_Message`.


Command_name: ``rmfile``
~~~~~~~~~~~~~~~~~~~~~~~~

This command removes the specified file.

``path``
    Value is a string.
    It specifies a path of a file to delete.

    If command succeeded, worker sends ``rc`` value 0 as an ``update`` message ``args`` key-value pair.

    Otherwise, worker sends ``update`` message with dictionary ``args`` key ``header`` with information about the error that occurred and another ``update`` message with dictionary ``args`` key ``rc`` with the error number.

    The basic structure of worker ``update`` message is explained in section :ref:`MsgPack_Keys_And_Values_Message`.


.. _MsgPack_Keys_And_Values_Message:


Contents of the value corresponding to ``args`` key in the dictionary of ``update`` request message
---------------------------------------------------------------------------------------------------

The ``args`` key-value pair describes information that the request message sends to master.
The value is a list of lists.
Each sub-list contains a name-value pair and represents a single update.
First element in a list represents the name of update (see below) and second element represents its value.
Commands may have their own update names so only common ones are described here.

``stdout``
    Value is a standard output of a process as a string.
    Some of the commands that master requests worker to start, may initiate processes which output a result as a standard output and this result is saved in the value of ``stdout``.
    The value satisfies the requirements described in a section below.

``rc``
    Value is an integer.
    It represents an exit code of a process.
    0 if the process exit was successful.
    Any other number represents a failure.

``header``
    Value is a string of a header.
    It represents additional information about how the command worked.
    For example, information may include the command name and arguments, working directory and environment or various errors or warnings of a process or other information that may be useful for debugging.
    The value satisfies the requirements described in a section below.

``files``
    Value is a list of strings.

    1) If the ``update`` message was a response to master request message ``start_command`` with a key value pair ``command_name`` and ``glob``, then strings in this list represent path names that matched pathname given by the master.

    2) If the ``update`` message was a response to master request message ``start_command`` with a key value pair ``command_name`` and ``listdir``, then strings in this list represent the names of the entries in the directory given by path, which master sent as an argument.

``stderr``
    Value is a standard error of a process as a string.
    Some of the commands that master requests worker to start may initiate processes which can output a result as a standard error and this result is saved in the value of ``stderr``.
    The value satisfies the requirements described in a section below.

``log``
    Value is a list where the first element represents the name of the log and the second element is a list, representing the contents of the file.
    The composition of this second element is described in the section below.
    This message is used to transfer the contents of the file that master requested worker to read.
    This file is identified by the name of the log.
    The same value is sent by master as the key of dictionary represented by ``logfile`` key within ``args`` dictionary of ``StartCommand`` command.

``elapsed``
    Value is an integer.
    It represents how much time has passed between the start of a command and the completion in seconds.

Requirements for content lists of ``stdout``, ``stderr``, ``header`` and ``log``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
The lists that represents the contents of the output or a file consist of three elements.

First element is a string with the content, which must be processed using the following algorithm:

* Each value may contain one or more lines (characters with a terminating ``\n`` character).
    Each line is not longer than internal ``maxsize`` value on worker side.
    Longer lines are split into multiple lines where each except the last line contains exactly ``maxsize`` characters and the last line may contain less.

* The lines are run through an internal worker cleanup regex.

Second element is a list of indexes, representing the positions of newline characters in the string of first tuple element.

Third element is a list of numbers, representing at what time each line was received as an output while processing the command.

The number of elements in both lists is always the same.
