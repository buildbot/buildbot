def sql_insert(dbapi, table, columns):
    """
    Make an SQL insert statement for the given table and columns, using the
    appropriate paramstyle for the dbi.  Note that this only supports positional
    parameters.  This will need to be reworked if Buildbot supports a backend with
    a name-based paramstyle.
    """

    if dbapi.paramstyle == 'qmark':
        params = ",".join(("?",)*len(columns))
    elif dbapi.paramstyle == 'numeric':
        params = ",".join(":%d" % d for d in range(1, len(columns)+1))
    elif dbapi.paramstyle == 'format':
        params = ",".join(("%s",)*len(columns))
    else:
        raise RuntimeError("unsupported paramstyle %s" % dbapi.paramstyle)
    return "INSERT INTO %s (%s) VALUES (%s)" % (table, ", ".join(columns), params)
