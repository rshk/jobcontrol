"""
Job control class.

.. warning::

    This class is (currently) **not** thread-safe!

    Thread-safety will be added in the future (includes storing the current
    job-control app in a thread-local object, filtering logs by thread id,
    etc.)
"""

from datetime import datetime, timedelta
import json
import logging

import psycopg2
import psycopg2.extras


class JobControl(object):
    table_prefix = 'jobcontrol_'

    def __init__(self, db_conf):
        """
        :param db_conf:
            Dictionary with the following keys: ``database``, ``user``,
            ``password``, ``host``, ``port``.
        """
        self.db_conf = db_conf
        pass

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
            kwargs TEXT
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

            -- Standard arguments
            args TEXT,
            created TIMESTAMP WITHOUT TIME ZONE,
            filename TEXT,
            funcName TEXT,
            levelname TEXT,
            levelno INTEGER,
            lineno INTEGER,
            module TEXT,
            msecs INTEGER,
            message TEXT,
            msg TEXT,
            name TEXT,
            pathname TEXT,
            process INTEGER,
            processName TEXT,
            relativeCreated INTEGER,
            thread INTEGER,
            threadName TEXT,

            -- Custom, to represent exception
            exc_class TEXT,
            exc_message TEXT,
            exc_repr TEXT,
            exc_traceback TEXT
        );
        """.format(prefix=self.table_prefix)

        with self.db, self.db.cursor() as cur:
            cur.execute(query)

    def drop_tables(self):
        with self.db, self.db.cursor() as cur:
            cur.execute('DROP TABLE "{prefix}job_run_log";'
                        .format(self.table_prefix))
            cur.execute('DROP TABLE "{prefix}job_run";'
                        .format(self.table_prefix))
            cur.execute('DROP TABLE "{prefix}job";'
                        .format(self.table_prefix))

    def define_job(self, function, args, kwargs):
        query = """
        INSERT INTO "{prefix}job" (ctime, function, args, kwargs)
        VALUES (%(ctime)s, %(function)s, %(args)s, %(kwargs)s)
        RETURNING id;
        """

        with self.db, self.db.cursor() as cur:
            cur.execute(query, {'ctime': datetime.now(),
                                'function': function,
                                'args': json.dumps(args),
                                'kwargs': json.dumps(kwargs)})
            return cur.fetchone()[0]

    def get_job_definition(self, job_id):
        query = """ SELECT * FROM "{prefix}job" WHERE id=%(id)s; """
        with self.db, self.db.cursor() as cur:
            cur.execute(query, {'id': job_id})
            return cur.fetchone()

    def undefine_job(self, job_id):
        query = """ DELETE FROM "{prefix}job" WHERE id=%(id)s; """
        with self.db, self.db.cursor() as cur:
            cur.execute(query, {'id': job_id})
            return cur.fetchone()[0]
        pass

    def iter_jobs(self):
        query = """ SELECT * FROM "{prefix}job" ORDER BY id ASC; """
        with self.db, self.db.cursor() as cur:
            cur.execute(query)
            for row in cur.fetchall():
                yield row

    def run_job(self, job_id):
        """Wrapper for job execution"""

        job_def = self.get_job_definition(job_id)

        if job_def is None:
            raise RuntimeError("No such job: {0}".format(job_id))

        job_run_id = self._create_job_run()

        handler = self.create_log_handler(job_id, job_run_id)
        root_logger = logging.getLogger('')
        root_logger.addHandler(handler)

        try:
            function = self._get_function(job_def['function'])
            args = json.loads(job_def['args'])
            kwargs = json.loads(job_def['kwargs'])

            # todo: before running, we want to make the controller instance
            #       globally available, for stuff like reporting progress
            #       and logging messages to the correct logger.
            #       We should use a threading.local for that, but first
            #       we need to write some tests..
            retval = function(*args, **kwargs)

        except Exception:  # anything will get logged
            pass

        else:
            pass

        finally:
            root_logger.removeHandler(handler)
            pass

    def create_log_handler(self, job_id, job_run_id):
        handler = PostgresLogHandler(
            self.db, self._table_name('job_run_log'),
            extra_info={'job_id': job_id, 'job_run_id': job_run_id})
        return handler

    def _create_job_run(self, job_id):
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

    def _update_jon_run(self, job_run_id, **kwargs):
        updatable_fields = set((
            'finished', 'success', 'progress_current', 'progress_total',
            'retval'))

        for k in kwargs:
            if k not in updatable_fields:
                raise ValueError("Field {0} cannot be updated!".format(k))

        kwargs['id'] = job_run_id

        if kwargs.get('finished', False):
            kwargs['end_time'] = datetime.now()

        set_query = []
        for key in kwargs:
            set_query.append("{0}=%({0})s".format(key))

        query = """
        UPDATE "{table_name}"
        SET {set_query}
        WHERE id=%(id)s;
        """.format(table_name=self._table_name('job_run'),
                   set_query=", ".join(set_query))

        with self.db, self.db.cursor() as cur:
            cur.execute(query, kwargs)

    def _get_function(self, name):
        module_name, function_name = name.split(':')
        # .... todo: import and return
        pass


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

    def serialize(self, record):
        """Prepare log record for insertion into PostgreSQL"""

        import traceback

        record_dict = {
            'args': json.dumps(record.args),
            'created': record.created,
            'filename': record.filename,
            'funcName': record.funcName,
            'levelname': record.levelname,
            'levelno': record.levelno,
            'lineno': record.lineno,
            'module': record.module,
            'msecs': record.msecs,
            'msg': record.msg,
            'name': record.name,
            'pathname': record.pathname,
            'process': record.process,
            'processName': record.processName,
            'relativeCreated': record.relativeCreated,
            'thread': record.thread,
            'threadName': record.threadName}

        if record.exc_info is not None:
            # We cannot serialize exception information.
            # The best workaround here is to simply add the
            # relevant information to the message, as the
            # formatter would..
            exc_class = u'{0}.{1}'.format(
                record.exc_info[0].__module__,
                record.exc_info[0].__name__)
            exc_message = str(record.exc_info[1])
            exc_repr = repr(record.exc_info[1])
            exc_traceback = '\n'.join(
                traceback.format_exception(*record.exc_info))

            # record_dict['_orig_msg'] = record_dict['msg']
            # record_dict['msg'] += "\n\n"
            # record_dict['msg'] += exc_traceback
            record_dict['exc_class'] = exc_class
            record_dict['exc_message'] = exc_message
            record_dict['exc_repr'] = exc_repr
            record_dict['exc_traceback'] = exc_traceback

        return record_dict

    def emit(self, record):
        """Handle a received log message"""

        data = self.serialize(record)
        data.update(self.extra_info)

        fields = [', '.join('"{0}"'.format(fld) for fld in data)]
        values = [', '.join('%({0})s'.format(fld) for fld in data)]
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
