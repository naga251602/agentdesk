# PostgreSQL Guide (sample corpus — original summary)

## What is PostgreSQL
PostgreSQL is an open-source object-relational database system known for reliability, extensibility, and strong SQL standards compliance. It supports advanced data types, full ACID transactions, and runs on all major operating systems. Many teams use PostgreSQL as their primary transactional store because it combines relational integrity with JSONB document storage in one engine.

## Connecting with psql
The psql command-line client connects to a server with a connection string such as postgres://user:password@host:5432/database. Inside psql, backslash commands inspect the database: \l lists databases, \dt lists tables, and \d followed by a table name describes that table's columns and indexes. You can quit the interactive session at any time with \q.

## Creating tables and constraints
A table is created with CREATE TABLE, and each column carries a data type such as integer, text, timestamp, or numeric. A primary key uniquely identifies every row and automatically creates a unique index. Foreign key constraints reference the primary key of another table and protect referential integrity, while CHECK constraints reject rows that violate a boolean rule you define.

## Indexes and query performance
An index speeds up lookups at the cost of slower writes and extra storage. PostgreSQL defaults to a B-tree index, which suits equality and range comparisons on ordered data. The EXPLAIN ANALYZE command shows the actual execution plan and timings for a query, revealing whether the planner chose a sequential scan or an index scan. A composite index on multiple columns helps queries that filter on those columns together, in the order the index defines them.

## JSONB columns
The jsonb data type stores JSON in a decomposed binary format that supports indexing and efficient key lookups. A GIN index on a jsonb column accelerates containment queries using the @> operator. Because jsonb discards insignificant whitespace and duplicate keys, it is usually preferred over the plain json type when you query inside the document rather than storing it verbatim.

## Transactions and isolation
Every statement in PostgreSQL runs inside a transaction, and you can group statements with BEGIN and COMMIT, or roll them back with ROLLBACK. The default isolation level is Read Committed, which prevents dirty reads but allows non-repeatable reads. Repeatable Read and Serializable levels give stronger guarantees; Serializable detects dangerous interleavings and aborts one transaction, so applications must be ready to retry.

## VACUUM and autovacuum
PostgreSQL uses multi-version concurrency control, so updates and deletes leave dead tuples behind in the table. The VACUUM process reclaims that space for reuse and prevents transaction ID wraparound. Autovacuum runs this maintenance automatically in the background, and heavily updated tables may need more aggressive autovacuum settings so bloat does not hurt query performance.

## Backup and restore
The pg_dump utility exports a database to a SQL script or archive file, and pg_restore loads an archive back into a database. For point-in-time recovery, you combine a base backup with continuous archiving of write-ahead log (WAL) segments. Managed and self-hosted deployments should test restores regularly, because an untested backup is only a hope, not a plan.

## Full text search
PostgreSQL can tokenise documents into tsvector values and queries into tsquery values, then match them with the @@ operator. A GIN index on a tsvector column makes full-text search fast enough for many support and documentation use cases without a separate search engine. Ranking functions such as ts_rank order results by how well they match the query terms.

## Connection pooling
Each PostgreSQL connection is a separate backend process, so thousands of idle application connections waste memory. A pooler such as PgBouncer sits between the application and the database and reuses a small set of server connections. Transaction pooling mode gives the highest connection reuse, but it is incompatible with session-level features like prepared statements held across transactions.
