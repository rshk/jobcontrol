"""
PostgreSQL-backed Job control class.

.. warning::

    This class is (currently) **not** thread-safe!

    Thread-safety will be added in the future (includes storing the current
    job-control app in a thread-local object, filtering logs by thread id,
    etc.)
"""

from datetime import datetime, timedelta
import logging
import pickle
import traceback

import psycopg2
import psycopg2.extras

from jobcontrol.base import JobControlBase


class PostgreSQLJobControl(JobControlBase):
    table_prefix = 'jobcontrol_'

    # ------------------------------------------------------------
    # Custom methods

    @property
    def db_conf(self):
        return self.config['DATABASE']

    def _table_name(self, name):
        return self.table_prefix + name

    @property
    def db(self):
        if getattr(self, '_db', None) is None:
            self._db = self.db_connect()
        return self._db

    def db_connect(self):
        conn = psycopg2.connect(**self.db_conf)
        conn.cursor_factory = psycopg2.extras.DictCursor
        conn.autocommit = False
        return conn

    def create_tables(self):
        query = """
        CREATE TABLE "{prefix}job" (
            id SERIAL PRIMARY KEY,
            ctime TIMESTAMP WITHOUT TIME ZONE,
            function TEXT,
            args TEXT,
            kwargs TEXT,
            dependencies INTEGER[]
        );

        CREATE TABLE "{prefix}job_run" (
            id SERIAL PRIMARY KEY,
            job_id INTEGER REFERENCES "{prefix}job" (id),
            start_time TIMESTAMP WITHOUT TIME ZONE,
            end_time TIMESTAMP WITHOUT TIME ZONE,
            started BOOLEAN DEFAULT false,
            finished BOOLEAN DEFAULT false,
            success BOOLEAN DEFAULT false,
            progress_current INTEGER DEFAULT 0,
            progress_total INTEGER DEFAULT 0,
            retval TEXT
        );

        CREATE TABLE "{prefix}job_run_log" (
            id SERIAL PRIMARY KEY,
            job_id INTEGER REFERENCES "{prefix}job" (id),
            job_run_id INTEGER REFERENCES "{prefix}job_run" (id),

            created TIMESTAMP WITHOUT TIME ZONE,
            levelno INTEGER,
            log_record TEXT

            -- Standard arguments
            -- "args" TEXT,
            -- "created" TIMESTAMP WITHOUT TIME ZONE,
            -- "filename" TEXT,
            -- "funcName" TEXT,
            -- "levelname" TEXT,
            -- "levelno" INTEGER,
            -- "lineno" INTEGER,
            -- "module" TEXT,
            -- "msecs" INTEGER,
            -- "message" TEXT,
            -- "msg" TEXT,
            -- "name" TEXT,
            -- "pathname" TEXT,
            -- "process" INTEGER,
            -- "processName" TEXT,
            -- "relativeCreated" INTEGER,
            -- "thread" INTEGER,
            -- "threadName" TEXT,

            -- Custom, to represent exception
            -- "exc_class" TEXT,
            -- "exc_message" TEXT,
            -- "exc_repr" TEXT,
            -- "exc_traceback" TEXT
        );
        """.format(prefix=self.table_prefix)

        with self.db, self.db.cursor() as cur:
            cur.execute(query)

    def drop_tables(self):
        with self.db, self.db.cursor() as cur:
            table_names = [self._table_name(x)
                           for x in ('job', 'job_run', 'job_run_log')]
            for table in table_names:
                cur.execute('DROP TABLE "{name}" CASCADE;'.format(name=table))

    # ------------------------------------------------------------
    # Installation methods

    def install(self):
        self.create_tables()

    def uninstall(self):
        self.drop_tables()

    # ------------------------------------------------------------
    # Job definition CRUD

    def _job_create(self, function, args, kwargs, dependencies=None):
        query = """
        INSERT INTO "{table_name}" (ctime, function, args, kwargs)
        VALUES (%(ctime)s, %(function)s, %(args)s, %(kwargs)s)
        RETURNING id;
        """.format(table_name=self._table_name('job'))

        if dependencies is None:
            dependencies = []

        with self.db, self.db.cursor() as cur:
            cur.execute(query, {
                'ctime': datetime.now(),
                'function': function,
                'args': self.pack(args),
                'kwargs': self.pack(kwargs),
                'dependencies': dependencies})
            return cur.fetchone()[0]

    def _job_read(self, job_id):
        with self.db, self.db.cursor() as cur:
            cur.execute("""
            SELECT * FROM "{table}" WHERE id=%(id)s;
            """.format(table=self._table_name('job')), {'id': job_id})
            data = cur.fetchone()
        if data is not None:
            data['args'] = self.unpack(data['args'])
            data['kwargs'] = self.unpack(data['kwargs'])
        return data

    def _job_update(self, job_id, **kwargs):
        if len(kwargs) < 1:
            return

        updargs = ['"{0}"=%({0})s'.format(k) for k in kwargs]
        query = """
        UPDATE "{table_name}" SET {args} WHERE id=%(id)s;
        """.format(
            table_name=self._table_name('job'),
            args=', '.join(updargs))
        kwargs['id'] = job_id

        if 'args' in kwargs:
            kwargs['args'] = self.pack(kwargs['args'])
        if 'kwargs' in kwargs:
            kwargs['kwargs'] = self.pack(kwargs['kwargs'])

        with self.db, self.db.cursor() as cur:
            cur.execute(query, kwargs)

    def _job_delete(self, job_id):
        with self.db, self.db.cursor() as cur:
            cur.execute("""
            DELETE FROM "{table}" WHERE job_id=%(id)s;
            """.format(table=self._table_name('job_run_log')), {'id': job_id})

            cur.execute("""
            DELETE FROM "{table}" WHERE job_id=%(id)s;
            """.format(table=self._table_name('job_run')), {'id': job_id})

            cur.execute("""
            DELETE FROM "{table}" WHERE id=%(id)s;
            """.format(table=self._table_name('job')), {'id': job_id})

    def _job_iter(self):
        query = """ SELECT * FROM "{table}" ORDER BY id ASC; """.format(
            table=self._table_name('job'))
        with self.db, self.db.cursor() as cur:
            cur.execute(query)
            for row in cur.fetchall():
                yield row['id']

    # ------------------------------------------------------------
    # Job run CRUD

    def _job_run_create(self, job_id):
        query = """
        INSERT INTO "{table_name}"
        (job_id, start_time, started, finished)
        VALUES (%(job_id)s, %(start_time)s, true, false)
        RETURNING id;
        """.format(table_name=self._table_name('job_run'))
        with self.db, self.db.cursor() as cur:
            cur.execute(query, {'job_id': job_id,
                                'start_time': datetime.now()})
            return cur.fetchone()[0]

    def _job_run_read(self, job_run_id):
        query = """ SELECT * FROM "{table}" WHERE id=%(id)s; """.format(
            table=self._table_name('job_run'))
        with self.db, self.db.cursor() as cur:
            cur.execute(query, {'id': job_run_id})
            data = cur.fetchone()
        if data is not None:
            data['retval'] = self.unpack(data['retval'])
        return data

    def _job_run_update(self, job_run_id, finished=None, success=None,
                        progress_current=None, progress_total=None,
                        retval=None):

        data = {'id': job_run_id}
        if finished is not None:
            data['finished'] = finished

        if finished:
            data['end_time'] = datetime.now()
            data['retval'] = self.pack(retval)

        if success is not None:
            data['success'] = success

        if progress_current is not None:
            data['progress_current'] = progress_current

        if progress_total is not None:
            data['progress_total'] = progress_total

        set_query = []
        for key in data:
            set_query.append("{0}=%({0})s".format(key))

        query = """
        UPDATE "{table_name}" SET {set_query} WHERE id=%(id)s;
        """.format(table_name=self._table_name('job_run'),
                   set_query=", ".join(set_query))

        with self.db, self.db.cursor() as cur:
            cur.execute(query, data)

    def _job_run_delete(self, job_run_id):
        query1 = 'DELETE FROM "{table_name}" WHERE id=%(id)s'.format(
            table_name=self._table_name('job_run'))
        query2 = 'DELETE FROM "{table_name}" WHERE job_run_id=%(id)s'.format(
            table_name=self._table_name('job_run_log'))

        with self.db, self.db.cursor() as cur:
            cur.execute(query2, {'id': job_run_id})
            cur.execute(query1, {'id': job_run_id})

    def _job_run_iter(self, job_id):
        query = """
        SELECT * FROM "{table_name}" WHERE job_id=%(id)s
        ORDER BY id ASC;
        """.format(table_name=self._table_name('job_run'))

        with self.db, self.db.cursor() as cur:
            cur.execute(query, {'id': job_id})

            for item in cur.fetchall():
                yield item

    # ------------------------------------------------------------
    # Logging

    def create_log_handler(self, job_id, job_run_id):
        handler = PostgresLogHandler(
            self.db, self._table_name('job_run_log'),
            extra_info={'job_id': job_id, 'job_run_id': job_run_id})
        handler.setLevel(logging.DEBUG)
        return handler

    def _iter_logs(self, job_run_id):
        query = """
        SELECT * FROM {table_name} ORDER BY created ASC;
        """.format(table_name=self._table_name('job_run_log'))
        with self.db, self.db.cursor() as cur:
            cur.execute(query)
            for item in cur.fetchall():
                yield pickle.loads(item['log_record'])


HOUR = 3600
DAY = 24 * HOUR
MONTH = 30 * DAY


class PostgresLogHandler(logging.Handler):
    """
    Logging handler writing to a PostgreSQL table.
    """

    log_retention_policy = {
        logging.DEBUG: 15 * DAY,
        logging.INFO: MONTH,
        logging.WARNING: 3 * MONTH,
        logging.ERROR: 6 * MONTH,
        logging.CRITICAL: 6 * MONTH,
    }
    log_max_retention = 12 * MONTH

    def __init__(self, db, table_name, extra_info=None):
        super(PostgresLogHandler, self).__init__()
        self.db = db
        self.table_name = table_name
        self.setLevel(logging.DEBUG)  # Log everything by default
        self.extra_info = {}
        if extra_info is not None:
            self.extra_info.update(extra_info)

    def flush(self):
        pass  # Nothing to flush!

    # def serialize(self, record):
    #     """Prepare log record for insertion into PostgreSQL"""

    #     import traceback

    #     record_dict = {
    #         'args': pickle.dumps(record.args),
    #         'created': datetime.utcfromtimestamp(record.created),
    #         'filename': record.filename,
    #         'funcName': record.funcName,
    #         'levelname': record.levelname,
    #         'levelno': record.levelno,
    #         'lineno': record.lineno,
    #         'module': record.module,
    #         'msecs': record.msecs,
    #         'msg': record.msg,
    #         'name': record.name,
    #         'pathname': record.pathname,
    #         'process': record.process,
    #         'processName': record.processName,
    #         'relativeCreated': record.relativeCreated,
    #         'thread': record.thread,
    #         'threadName': record.threadName}

    #     if record.exc_info is not None:
    #         # We cannot serialize exception information.
    #         # The best workaround here is to simply add the
    #         # relevant information to the message, as the
    #         # formatter would..
    #         exc_class = u'{0}.{1}'.format(
    #             record.exc_info[0].__module__,
    #             record.exc_info[0].__name__)
    #         exc_message = str(record.exc_info[1])
    #         exc_repr = repr(record.exc_info[1])
    #         exc_traceback = '\n'.join(
    #             traceback.format_exception(*record.exc_info))

    #         # record_dict['_orig_msg'] = record_dict['msg']
    #         # record_dict['msg'] += "\n\n"
    #         # record_dict['msg'] += exc_traceback
    #         record_dict['exc_class'] = exc_class
    #         record_dict['exc_message'] = exc_message
    #         record_dict['exc_repr'] = exc_repr
    #         record_dict['exc_traceback'] = exc_traceback

    #     return record_dict

    def emit(self, record):
        """Handle a received log message"""

        from jobcontrol.globals import execution_context

        if record.exc_info is not None:
            # We cannot serialize exception information.
            # The best workaround here is to simply add the
            # relevant information to the message, as the
            # formatter would..

            exc_class, exc_msg, exc_tb = record.exc_info
            exc_traceback = '\n'.join(
                traceback.format_exception(*record.exc_info))

            record.exc_info = exc_class, exc_msg, exc_traceback

        data = {
            'job_id': execution_context.job_id,
            'job_run_id': execution_context.job_run_id,
            'created': datetime.utcfromtimestamp(record.created),
            'levelno': record.levelno,
            'log_record': pickle.dumps(record),
        }

        # data = self.serialize(record)

        fields = ', '.join('"{0}"'.format(fld) for fld in data)
        values = ', '.join('%({0})s'.format(fld) for fld in data)
        query = """
        INSERT INTO "{table}" ({fields}) VALUES ({values});
        """.format(table=self.table_name, fields=fields, values=values)

        with self.db, self.db.cursor() as cur:
            cur.execute(query, data)

    def cleanup_old_messages(self):
        """Delete old log messages, according to log retention policy"""

        query = """
        DELETE FROM "{0}"
        WHERE "levelno" <= %(levelno)s
          AND "created" <= %(expiredate)s;
        """.format(self.table_name)

        # Apply log retention policy
        for minlevel, retention in self.log_retention_policy.iteritems():
            expiredate = datetime.now() - timedelta(seconds=retention)
            with self.db, self.db.cursor() as cur:
                cur.execute(query, {'levelno': minlevel,
                                    'expiredate': expiredate})

        # Delete all the logs older than self.log_max_retention
        expiredate = datetime.now() - timedelta(seconds=self.log_max_retention)
        query = """
        DELETE FROM "{0}" WHERE "created" <= %(expiredate)s;
        """.format(self.table_name)
        with self.db, self.db.cursor() as cur:
            cur.execute(query, {'expiredate': expiredate})
