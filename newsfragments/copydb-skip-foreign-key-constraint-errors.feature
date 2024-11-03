Added ``ignore-fk-error-rows`` option to ``copy-db`` script. It allows ignoring
all rows that fail foreign key constraint checks. This is useful in cases when
migrating from a database engine that does not support foreign key constraints
to one that does.
