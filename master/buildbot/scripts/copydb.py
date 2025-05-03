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


from __future__ import annotations

import os
import queue
from typing import TYPE_CHECKING
from typing import Any
from typing import Callable

import sqlalchemy as sa
from twisted.internet import defer

from buildbot import config as config_module
from buildbot.db import connector
from buildbot.db import exceptions
from buildbot.db import model
from buildbot.master import BuildMaster
from buildbot.scripts import base
from buildbot.util import in_reactor
from buildbot.util import misc

if TYPE_CHECKING:
    from buildbot.util.twisted import InlineCallbacksType


@in_reactor
def copy_database(config: dict) -> defer.Deferred:  # pragma: no cover
    # we separate the actual implementation to protect unit tests
    # from @in_reactor which stops the reactor
    return _copy_database_in_reactor(config)


@defer.inlineCallbacks
def _copy_database_in_reactor(config: dict) -> InlineCallbacksType[int]:
    if not base.checkBasedir(config):
        return 1

    print_debug = not config["quiet"]
    ignore_fk_error_rows = config['ignore-fk-error-rows']

    def print_log(*args: Any, **kwargs: Any) -> None:
        if print_debug:
            print(*args, **kwargs)

    config['basedir'] = os.path.abspath(config['basedir'])

    with base.captureErrors(
        (SyntaxError, ImportError), f"Unable to load 'buildbot.tac' from '{config['basedir']}':"
    ):
        config_file = base.getConfigFileFromTac(config['basedir'])

    if not config_file:
        return 1

    with base.captureErrors(
        config_module.ConfigErrors, f"Unable to load '{config_file}' from '{config['basedir']}':"
    ):
        master_src_cfg = base.loadConfig(config, config_file)
        master_dst_cfg = base.loadConfig(config, config_file)

    if not master_src_cfg or not master_dst_cfg:
        return 1

    master_dst_cfg.db.db_url = config["destination_url"]

    print_log(f"Copying database ({master_src_cfg.db.db_url}) to ({config['destination_url']})")

    if not master_src_cfg or not master_dst_cfg:
        return 1

    master_src = None
    master_dst = None
    try:
        master_src = BuildMaster(config['basedir'])
        master_src.config = master_src_cfg
        try:
            yield master_src.db.setup(check_version=True, verbose=not config["quiet"])
        except exceptions.DatabaseNotReadyError:
            for l in connector.upgrade_message.format(basedir=config['basedir']).split('\n'):
                print(l)
            return 1

        master_dst = BuildMaster(config['basedir'])
        master_dst.config = master_dst_cfg
        yield master_dst.db.setup(check_version=False, verbose=not config["quiet"])
        yield master_dst.db.model.upgrade()
        yield _copy_database_with_db(master_src.db, master_dst.db, ignore_fk_error_rows, print_log)
    finally:
        for master in (master_src, master_dst):
            if master is not None and master.db.pool is not None:
                yield master.db.pool.stop()

    return 0


def _thd_check_row_foreign_keys(
    table_name: str,
    row_dict: dict[str, Any],
    column_name: str,
    id_rows: set[Any],
    print_log: Callable[..., None],
) -> bool:
    if column_name not in row_dict:
        return True

    value = row_dict[column_name]
    if value is None:
        return True

    if value not in id_rows:
        row_str = repr(row_dict)[0:200]
        print_log(
            f'Ignoring row from {table_name} because {column_name}={value} foreign key '
            f'constraint failed. Row: {row_str}'
        )
        return False

    return True


def _thd_check_rows_foreign_keys(
    table_name: str,
    row_dicts: list[dict[str, Any]],
    column_name: str,
    id_rows: set[Any],
    print_log: Callable[..., None],
) -> list[dict[str, Any]]:
    return [
        row_dict
        for row_dict in row_dicts
        if _thd_check_row_foreign_keys(table_name, row_dict, column_name, id_rows, print_log)
    ]


@defer.inlineCallbacks
def _copy_single_table(
    metadata: Any,
    src_db: Any,
    dst_db: Any,
    table_name: str,
    buildset_to_parent_buildid: list[tuple[int, int]],
    buildset_to_rebuilt_buildid: list[tuple[int, int]],
    ignore_fk_error_rows: bool,
    print_log: Callable[..., None],
) -> InlineCallbacksType[None]:
    table = metadata.tables[table_name]
    column_keys = table.columns.keys()

    rows_queue: queue.Queue[Any] = queue.Queue(32)
    written_count = [0]
    total_count = [0]

    autoincrement_foreign_key_column = None
    foreign_key_check_columns = []

    for column_name, column in table.columns.items():
        if not column.foreign_keys and column.primary_key and isinstance(column.type, sa.Integer):
            autoincrement_foreign_key_column = column_name

        for fk in column.foreign_keys:
            if table_name == 'buildsets' and column_name in ('parent_buildid', 'rebuilt_buildid'):
                continue
            if table_name == 'changes' and column_name in ('parent_changeids',):
                # TODO: not currently handled because column refers to the same table
                continue
            foreign_key_check_columns.append((column_name, fk.column))

    def tdh_query_all_column_rows(conn: sa.engine.Connection, column: sa.Column) -> set[Any]:
        q = sa.select(column).select_from(column.table)
        result = conn.execute(q)

        # Load data incrementally in order to control maximum used memory size
        ids = set()
        while True:
            chunk = result.fetchmany(10000)
            if not chunk:
                break
            for row in chunk:
                ids.add(getattr(row, column.name))
        return ids

    got_error = False

    def thd_write(conn: sa.engine.Connection) -> None:
        max_column_id = 0

        foreign_key_check_rows = []
        if ignore_fk_error_rows:
            foreign_key_check_rows = [
                (column_name, tdh_query_all_column_rows(conn, fk_column))
                for column_name, fk_column in foreign_key_check_columns
            ]

        while True:
            try:
                rows = rows_queue.get(timeout=1)
                if rows is None:
                    if autoincrement_foreign_key_column is not None and max_column_id != 0:
                        if dst_db.pool.engine.dialect.name == 'postgresql':
                            # Explicitly inserting primary row IDs does not bump the primary key
                            # sequence on Postgres
                            seq_name = f"{table_name}_{autoincrement_foreign_key_column}_seq"
                            transaction = conn.begin()
                            conn.execute(
                                sa.text(
                                    f"ALTER SEQUENCE {seq_name} RESTART WITH {max_column_id + 1}"
                                )
                            )
                            transaction.commit()

                    rows_queue.task_done()
                    return

                row_dicts = [{k: getattr(row, k) for k in column_keys} for row in rows]

                if autoincrement_foreign_key_column is not None:
                    for row in row_dicts:
                        max_column_id = max(max_column_id, row[autoincrement_foreign_key_column])

                if ignore_fk_error_rows:
                    for column_name, id_rows in foreign_key_check_rows:
                        row_dicts = _thd_check_rows_foreign_keys(
                            table_name, row_dicts, column_name, id_rows, print_log
                        )

                if table_name == "buildsets":
                    for row_dict in row_dicts:
                        if row_dict["parent_buildid"] is not None:
                            buildset_to_parent_buildid.append((
                                row_dict["id"],
                                row_dict["parent_buildid"],
                            ))
                        row_dict["parent_buildid"] = None

                        if row_dict['rebuilt_buildid'] is not None:
                            buildset_to_rebuilt_buildid.append((
                                row_dict['id'],
                                row_dict['rebuilt_buildid'],
                            ))
                        row_dict['rebuilt_buildid'] = None

            except queue.Empty:
                continue
            except Exception:
                nonlocal got_error
                got_error = True
                # unblock queue
                try:
                    rows_queue.get(timeout=1)
                    rows_queue.task_done()
                except queue.Empty:
                    pass
                raise

            try:
                written_count[0] += len(rows)
                print_log(
                    f"Copying {len(rows)} items ({written_count[0]}/{total_count[0]}) "
                    f"for {table_name} table"
                )

                if len(row_dicts) > 0:
                    conn.execute(table.insert(), row_dicts)
                    conn.commit()

            finally:
                rows_queue.task_done()

    def thd_read(conn: sa.engine.Connection) -> None:
        q = sa.select(sa.sql.func.count()).select_from(table)
        total_count[0] = conn.execute(q).scalar() or 0

        result = conn.execute(sa.select(table))
        while not got_error:
            chunk = result.fetchmany(10000)
            if not chunk:
                break
            rows_queue.put(chunk)

        rows_queue.put(None)

    error: Exception | None = None
    tasks = [src_db.pool.do(thd_read), dst_db.pool.do(thd_write)]
    for d in tasks:
        try:
            yield d
        except Exception as e:
            error = e

    rows_queue.join()

    if error is not None:
        raise error


@defer.inlineCallbacks
def _copy_database_with_db(
    src_db: Any, dst_db: Any, ignore_fk_error_rows: bool, print_log: Callable[..., None]
) -> InlineCallbacksType[None]:
    # Tables need to be specified in correct order so that tables that other tables depend on are
    # copied first.
    table_names = [
        # Note that buildsets.parent_buildid and rebuilt_buildid introduce circular dependency.
        # They are handled separately
        "buildsets",
        "buildset_properties",
        "projects",
        "codebases",
        "codebase_commits",
        "codebase_branches",
        "builders",
        "changesources",
        "buildrequests",
        "workers",
        "masters",
        "buildrequest_claims",
        "changesource_masters",
        "builder_masters",
        "configured_workers",
        "connected_workers",
        "patches",
        "sourcestamps",
        "buildset_sourcestamps",
        "changes",
        "change_files",
        "change_properties",
        "users",
        "users_info",
        "change_users",
        "builds",
        "build_properties",
        "build_data",
        "steps",
        "logs",
        "logchunks",
        "schedulers",
        "scheduler_masters",
        "scheduler_changes",
        "tags",
        "builders_tags",
        "test_result_sets",
        "test_names",
        "test_code_paths",
        "test_results",
        "objects",
        "object_state",
    ]

    metadata = model.Model.metadata
    assert len(set(table_names)) == len(set(metadata.tables.keys()))

    # Not a dict so that the values are inserted back in predictable order
    buildset_to_parent_buildid: list[tuple[int, int]] = []
    buildset_to_rebuilt_buildid: list[tuple[int, int]] = []

    for table_name in table_names:
        yield _copy_single_table(
            metadata,
            src_db,
            dst_db,
            table_name,
            buildset_to_parent_buildid,
            buildset_to_rebuilt_buildid,
            ignore_fk_error_rows,
            print_log,
        )

    def thd_write_buildset_parent_buildid(conn: sa.engine.Connection) -> None:
        written_count = 0
        for rows in misc.chunkify_list(buildset_to_parent_buildid, 10000):
            q = model.Model.buildsets.update()
            q = q.where(model.Model.buildsets.c.id == sa.bindparam('_id'))
            q = q.values({'parent_buildid': sa.bindparam('parent_buildid')})

            written_count += len(rows)
            print_log(
                f"Copying {len(rows)} items ({written_count}/{len(buildset_to_parent_buildid)}) "
                f"for buildset.parent_buildid field"
            )

            conn.execute(
                q,
                [
                    {'_id': buildset_id, 'parent_buildid': parent_buildid}
                    for buildset_id, parent_buildid in rows
                ],
            )

    yield dst_db.pool.do(thd_write_buildset_parent_buildid)

    def thd_write_buildset_rebuilt_buildid(conn: sa.engine.Connection) -> None:
        written_count = 0
        for rows in misc.chunkify_list(buildset_to_rebuilt_buildid, 10000):
            q = model.Model.buildsets.update()
            q = q.where(model.Model.buildsets.c.id == sa.bindparam('_id'))
            q = q.values({'rebuilt_buildid': sa.bindparam('rebuilt_buildid')})

            written_count += len(rows)
            print_log(
                f"Copying {len(rows)} items ({written_count}/{len(buildset_to_rebuilt_buildid)}) "
                f"for buildset.rebuilt_buildid field"
            )

            conn.execute(
                q,
                [
                    {'_id': buildset_id, 'rebuilt_buildid': rebuilt_buildid}
                    for buildset_id, rebuilt_buildid in rows
                ],
            )

    yield dst_db.pool.do(thd_write_buildset_rebuilt_buildid)

    print_log("Copy complete")
