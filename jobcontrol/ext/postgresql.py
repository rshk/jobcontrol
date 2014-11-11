"""
PostgreSQL-backed Job control class.
"""

from datetime import datetime, timedelta
from urlparse import urlparse, parse_qs
import traceback

import psycopg2
import psycopg2.extras

from jobcontrol.interfaces import StorageBase
from jobcontrol.utils import cached_property
from jobcontrol.exceptions import NotFound
from werkzeug.local import Local


class PostgreSQLStorage(StorageBase):
    def __init__(self, dbconf, table_prefix='jobcontrol_'):
        self._dbconf = dbconf
        if table_prefix is None:
            table_prefix = ''
        self._table_prefix = table_prefix
        # self._local = Local()
        self._db = None

    @classmethod
    def from_url(cls, url):
        parsed = urlparse(url)
        if parsed.scheme != 'postgresql':
            raise ValueError("Unsupported scheme: {0}".format(parsed.scheme))

        dbconf = {
            'database': parsed.path.split('/')[1],
            'user': parsed.username,
            'password': parsed.password,
            'host': parsed.hostname,
            'port': parsed.port or 5432,
        }

        kwargs = {k: v[0] for k, v in parse_qs(parsed.query).iteritems()}

        return cls(dbconf, **kwargs)

    def __deepcopy__(self, memo):
        """
        The deepcopy is used when we want to use this guy in another thread /
        process / whatever. Since the psycopg2 connection is not thread-safe,
        we cannot share it -> instead, we do a copy.
        """
        return PostgreSQLStorage(self._dbconf, table_prefix=self._table_prefix)

    @property
    def db(self):
        if self._db is None or self._db.closed:
            self._db = self._connect()
        return self._db
        # try:
        #     return self._local.db
        # except AttributeError:
        #     self._local.db = self._connect()
        #     return self._local.db

    def _connect(self):
        conn = psycopg2.connect(**self._dbconf)
        conn.cursor_factory = psycopg2.extras.DictCursor
        conn.autocommit = False
        return conn

    def install(self):
        self._create_tables()

    def uninstall(self):
        self._drop_tables()

    def _create_tables(self):
        query = """
        CREATE TABLE "{prefix}job" (
            id SERIAL PRIMARY KEY,
            title TEXT,
            function TEXT,
            args TEXT,
            kwargs TEXT,
            ctime TIMESTAMP WITHOUT TIME ZONE,
            mtime TIMESTAMP WITHOUT TIME ZONE,
            dependencies INTEGER[]
        );

        CREATE TABLE "{prefix}build" (
            id SERIAL PRIMARY KEY,
            job_id INTEGER REFERENCES "{prefix}job" (id),
            start_time TIMESTAMP WITHOUT TIME ZONE,
            end_time TIMESTAMP WITHOUT TIME ZONE,
            started BOOLEAN DEFAULT false,
            finished BOOLEAN DEFAULT false,
            success BOOLEAN DEFAULT false,
            skipped BOOLEAN DEFAULT false,
            progress_current INTEGER DEFAULT 0,
            progress_total INTEGER DEFAULT 0,
            retval TEXT,
            exception TEXT,
            exception_tb TEXT
        );

        CREATE TABLE "{prefix}log" (
            id SERIAL PRIMARY KEY,
            job_id INTEGER REFERENCES "{prefix}job" (id),
            build_id INTEGER REFERENCES "{prefix}build" (id),
            created TIMESTAMP WITHOUT TIME ZONE,
            level INTEGER,
            record TEXT
        );
        """.format(prefix=self._table_prefix)

        with self.db, self.db.cursor() as cur:
            cur.execute(query)

    def _drop_tables(self):
        table_names = [self._table_name(x) for x in ('job', 'build', 'log')]
        with self.db, self.db.cursor() as cur:
            for table in reversed(table_names):
                cur.execute('DROP TABLE "{name}" CASCADE;'.format(name=table))

    def _table_name(self, name):
        return '{0}{1}'.format(self._table_prefix, name)

    def _escape_name(self, name):
        """Escape a name for use as field name"""
        return '"{0}"'.format(name)

    # -------------------- Query building --------------------

    def _query_insert(self, table, data):
        _fields = sorted(data)
        return """
        INSERT INTO "{table}" ({fields})
        VALUES ({valspec}) RETURNING id;
        """.format(
            table=self._table_name(table),
            fields=', '.join(self._escape_name(x) for x in _fields),
            valspec=', '.join('%({0})s'.format(x) for x in _fields))

    def _query_update(self, table, data):
        _fields = [x for x in sorted(data) if x != 'id']
        return """
        UPDATE "{table}" SET {updates} WHERE "id"=%(id)s;
        """.format(
            table=self._table_name(table),
            updates=', '.join(
                "{0}=%({1})s".format(self._escape_name(fld), fld)
                for fld in _fields))

    def _query_select_one(self, table, fields='*'):
        return """
        SELECT {fields} FROM "{table}" WHERE "id"=%(id)s;
        """.format(table=self._table_name(table),
                   fields=fields)

    def _query_delete_one(self, table):
        return """
        DELETE FROM "{table}" WHERE "id"=%(id)s;
        """.format(table=self._table_name(table))

    def _query_select(self, table, fields='*', filters=None, order=None,
                      offset=None, limit=None):

        query_parts = ["SELECT {0} FROM {1}".format(
            fields, self._table_name(table))]

        if filters is not None:
            query_parts.append('WHERE {0}'.format(' AND '.join(filters)))

        if order is not None:
            if not isinstance(order, basestring):
                order = ', '.join(order)
            query_parts.append('ORDER BY {0}'.format(order))

        if offset is not None:
            query_parts.append('OFFSET {0}'.format(int(offset)))

        if limit is not None:
            query_parts.append('LIMIT {0}'.format(int(limit)))

        return ' '.join(query_parts) + ';'

    # -------------------- Query running --------------------

    def _do_insert(self, table, data):
        query = self._query_insert(table, data)
        with self.db, self.db.cursor() as cur:
            cur.execute(query, data)
            return cur.fetchone()[0]

    def _do_update(self, table, data):
        query = self._query_update(table, data)
        with self.db, self.db.cursor() as cur:
            cur.execute(query, data)

    def _do_select_one(self, table, pk):
        query = self._query_select_one(table)
        with self.db, self.db.cursor() as cur:
            cur.execute(query, {'id': pk})
            return cur.fetchone()

    def _do_delete_one(self, table, pk):
        query = self._query_delete_one(table)
        with self.db, self.db.cursor() as cur:
            cur.execute(query, {'id': pk})

    def _do_select(self, table, **kw):
        query = self._query_select(table, **kw)
        with self.db, self.db.cursor() as cur:
            cur.execute(query)
            for item in cur.fetchall():
                yield item

    # -------------------- Object serialization --------------------

    def _job_pack(self, job):
        if job.get('args') is not None:
            job['args'] = self.pack(job['args'])
        if job.get('kwargs') is not None:
            job['kwargs'] = self.pack(job['kwargs'])
        return job

    def _job_unpack(self, row):
        row = dict(row)
        if row.get('args') is not None:
            row['args'] = self.unpack(row['args'])
        if row.get('kwargs') is not None:
            row['kwargs'] = self.unpack(row['kwargs'])
        return row

    def _build_pack(self, job):
        if job.get('retval') is not None:
            job['retval'] = self.pack(job['retval'])
        if job.get('exception') is not None:
            job['exception'] = self.pack(job['exception'])
        return job

    def _build_unpack(self, row):
        row = dict(row)

        if row.get('retval') is not None:
            row['retval'] = self.unpack(row['retval'], safe=True)

        if row.get('exception') is not None:
            row['exception'] = self.unpack(row['exception'], safe=True)

        return row

    # ------------------------------------------------------------
    # Job CRUD methods
    # ------------------------------------------------------------

    def create_job(self, function, args=None, kwargs=None, dependencies=None,
                   title=None):
        data = self._job_pack({
            'function': function,
            'args': args or (),
            'kwargs': kwargs or {},
            'dependencies': dependencies or [],
            'title': title,
            'ctime': datetime.now(),
            'mtime': datetime.now(),
        })

        return self._do_insert('job', data)

    def update_job(self, job_id, function=None, args=None, kwargs=None,
                   dependencies=None, title=None):

        if self.get_job(job_id) is None:
            raise NotFound('No such job: {0}'.format(job_id))

        data = {'id': job_id}

        if function is not None:
            data['function'] = function

        if args is not None:
            data['args'] = self.pack(args)

        if kwargs is not None:
            data['kwargs'] = self.pack(kwargs)

        if dependencies is not None:
            data['dependencies'] = dependencies

        if title is not None:
            data['title'] = title

        if len(data) <= 1:
            return  # nothing to update

        self._do_update('job', data)

    def get_job(self, job_id):
        data = self._do_select_one('job', job_id)

        if data is None:
            raise NotFound('No such job: {0}'.format(job_id))

        return self._job_unpack(data)

    def delete_job(self, job_id):
        query = 'DELETE FROM "{table}" WHERE "job_id"=%(job_id)s'.format(
            table=self._table_name('log'))

        with self.db, self.db.cursor() as cur:
            cur.execute(query, {'job_id': job_id})

        query = 'DELETE FROM "{table}" WHERE "job_id"=%(job_id)s'.format(
            table=self._table_name('build'))

        with self.db, self.db.cursor() as cur:
            cur.execute(query, {'job_id': job_id})

        self._do_delete_one('job', job_id)

    def list_jobs(self):
        query = 'SELECT id FROM "{table}" ORDER BY id ASC;'.format(
            table=self._table_name('job'))

        with self.db, self.db.cursor() as cur:
            cur.execute(query)
            return [r['id'] for r in cur.fetchall()]

    def iter_jobs(self):
        for item in self._do_select('job', order='id ASC'):
            yield self._job_unpack(item)

    def mget_jobs(self, job_ids):
        # todo: there should be a better way to do this!
        jobs = []
        for j in job_ids:
            try:
                jobs.append(self.get_job(j))
            except NotFound:
                pass
        return jobs

    def get_job_deps(self, job_id):
        """Get direct job dependencies"""
        query = """
        SELECT * FROM "{table}" WHERE id IN (
            SELECT unnest(dependencies) FROM "{table}"
            WHERE id=%(id)s) ORDER BY id ASC;
        """.format(table=self._table_name('job'))
        with self.db, self.db.cursor() as cur:
            cur.execute(query, {'id': job_id})
            return [self._job_unpack(x) for x in cur.fetchall()]

    def get_job_revdeps(self, job_id):
        query = """
        SELECT * FROM "{table}"
        WHERE dependencies @> ARRAY[%(id)s]
        ORDER BY id ASC;
        """.format(table=self._table_name('job'))
        with self.db, self.db.cursor() as cur:
            cur.execute(query, {'id': job_id})
            return [self._job_unpack(x) for x in cur.fetchall()]

    def get_job_builds(self, job_id, started=None, finished=None,
                       success=None, skipped=None, order='asc', limit=100):
        """
        Get all the builds for a job, sorted by date, according
        to the order specified by ``order``.

        :param job_id:
            The job id
        :param started:
            If set to a boolean, filter on the "started" field
        :param finished:
            If set to a boolean, filter on the "finished" field
        :param success:
            If set to a boolean, filter on the "success" field
        :param skipped:
            If set to a boolean, filter on the "skipped" field
        :param order:
            'asc' (default) or 'desc'
        :param limit:
            only return the first ``limit`` builds
        """

        wheres = ['"job_id"=%(job_id)s']
        data = {'job_id': job_id}

        filters = [
            ('started', started),
            ('finished', finished),
            ('success', success),
            ('skipped', skipped),
        ]

        for key, val in filters:
            if val is not None:
                wheres.append('"{0}"=%({0})s'.format(key))
                data[key] = val

        query = "SELECT * FROM {table} WHERE {wheres}".format(
            table=self._table_name('build'),
            wheres=' AND '.join(wheres))

        order = order.lower()

        if order == 'asc':
            query += ' ORDER BY id ASC'

        elif order == 'desc':
            query += ' ORDER BY id DESC'

        else:
            raise ValueError("Invalid order direction: {0}".format(order))

        if limit is not None:
            query += ' LIMIT %(limit)s'
            data['limit'] = limit

        query += ';'

        with self.db, self.db.cursor() as cur:
            cur.execute(query, data)
            for x in cur.fetchall():
                yield self._build_unpack(x)

    # ------------------------------------------------------------
    # Build CRUD methods
    # ------------------------------------------------------------

    def create_build(self, job_id):
        return self._do_insert('build', {'job_id': job_id})

    def get_build(self, build_id):
        build = self._do_select_one('build', build_id)
        if build is None:
            raise NotFound('Build not found: {0}'.format(build_id))
        return self._build_unpack(build)

    def delete_build(self, build_id):
        self._do_delete_one('build', build_id)

    def start_build(self, build_id):
        self._do_update('build', {
            'id': build_id,
            'start_time': datetime.now(),
            'started': True,
        })

    def finish_build(self, build_id, success=True, skipped=False, retval=None,
                     exception=None, exc_info=None):

        exc_trace = None
        if exc_info is not None:
            exc_trace = ''.join(traceback.format_exception(*exc_info))

        self._do_update('build', self._build_pack({
            'id': build_id,
            'end_time': datetime.now(),
            'finished': True,
            'success': success,
            'skipped': skipped,
            'retval': retval,
            'exception': exception,
            'exception_tb': exc_trace,
        }))

    def update_build_progress(self, build_id, current, total):
        self._do_update('build', self._build_pack({
            'id': build_id,
            'progress_current': current,
            'progress_total': total,
        }))

    def log_message(self, job_id, build_id, record):
        self._do_insert('log', {
            'job_id': job_id,
            'build_id': build_id,
            'created': datetime.utcfromtimestamp(record.created),
            'level': record.levelno,
            'record': self.pack(record)
        })

    def prune_log_messages(self, job_id=None, build_id=None,
                           max_age=None, level=None):
        """
        Delete old log messages.

        :param job_id:
            If specified, only delete messages for this job

        :param build_id:
            If specified, only delete messages for this build

        :param max_age:
            If specified, only delete log messages with an age
            greater than this one (in seconds)

        :param level:
            If specified, only delete log messages with a level
            equal minor to this one
        """

        conditions = []
        filters = {}

        if job_id is not None:
            conditions.append('"job_id"=%(job_id)s')
            filters['job_id'] = job_id

        if build_id is not None:
            conditions.append('"build_id"=%(build_id)s')
            filters['build_id'] = build_id

        if max_age is not None:
            expire_date = datetime.now() - timedelta(seconds=max_age)
            conditions.append('"created" < %(expire_date)s')
            filters['expire_date'] = expire_date

        if level is not None:
            conditions.append('"level" < %(level)s')
            filters['level'] = level

        query = 'DELETE FROM "{0}"'.format(self._table_name('log'))

        if len(conditions) > 0:
            query += ' WHERE {0}'.format(' AND '.join(conditions))

        query += ';'

        with self.db, self.db.cursor() as cur:
            cur.execute(query, filters)

    def iter_log_messages(self, job_id=None, build_id=None, max_date=None,
                          min_date=None, min_level=None):

        conditions = []
        filters = {}

        if job_id is not None:
            conditions.append('"job_id"=%(job_id)s')
            filters['job_id'] = job_id

        if build_id is not None:
            conditions.append('"build_id"=%(build_id)s')
            filters['build_id'] = build_id

        if max_date is not None:
            conditions.append('"created" < %(max_date)s')
            filters['max_date'] = max_date

        if min_date is not None:
            conditions.append('"created" >= %(min_date)s')
            filters['min_date'] = min_date

        if min_level is not None:
            conditions.append('"level" >= %(min_level)s')
            filters['min_level'] = min_level

        query = 'SELECT * FROM "{0}"'.format(self._table_name('log'))

        if len(conditions) > 0:
            query += ' WHERE {0}'.format(' AND '.join(conditions))

        query += ' ORDER BY created ASC'

        query += ';'

        with self.db, self.db.cursor() as cur:
            cur.execute(query, filters)
            for item in cur.fetchall():
                record = self.unpack(item['record'])

                # todo: any better way to do this?
                record.job_id = item['job_id']
                record.build_id = item['build_id']

                # Make sure we're dealing with unicode..
                if not hasattr(record, 'message'):
                    # Why is this sometimes not set?
                    record.message = record.getMessage()

                if isinstance(record.message, bytes):
                    record.message = record.message.decode('utf-8')

                yield record
