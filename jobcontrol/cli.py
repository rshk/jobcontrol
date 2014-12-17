import click
import logging
from nicelog.formatters import ColorLineFormatter
from prettytable import PrettyTable
import sys

from jobcontrol.core import JobControl
from jobcontrol.utils import json_dumps


logger = logging.getLogger('')
logger.setLevel(logging.DEBUG)

handler = logging.StreamHandler(sys.stderr)
handler.setFormatter(ColorLineFormatter(
    show_date=True, show_function=True, show_filename=True,
    message_inline=False))
handler.setLevel(logging.DEBUG)

logger.addHandler(handler)


def cli_main(jc_app):
    pass


config = None
jc = None
output_fmt = None


DATE_FMT = '%Y-%m-%d %H:%M'


def _fmt_date(dt):
    if dt is None:
        return ''
    return dt.strftime(DATE_FMT)


def _fmt_bool(val, inv=False):
    col = '\x1b[32m' if bool(val) ^ bool(inv) else '\x1b[31m'
    return '{0}{1}\x1b[0m'.format(col, val)


def _fmt_progress(cur, tot):
    if tot == 0:
        return 'N/A'
    return '{0}/{1} ({2:.1f}%)'.format(cur, tot, cur * 100.0 / tot)


@click.group()
@click.option('--config-file', metavar='FILE',
              help='Path to YAML configuration file')
# @click.option('--storage', metavar='FILE', help='Storage URL')
@click.option('--format', 'outfmt', default='human',
              help='Output format. "human" or "json" (default: "human").',
              type=click.Choice(('json', 'human')))
def cli_main_grp(config_file, outfmt):
    # todo: use pass_context for passing context instead of global objects?

    global jc, output_fmt

    output_fmt = outfmt

    if config_file is None:
        raise ValueError('Configuration file missing')

    jc = JobControl.from_config_file(config_file)


@cli_main_grp.command()
def install():
    jc.storage.install()


@cli_main_grp.command()
def uninstall():
    jc.storage.uninstall()


@cli_main_grp.command()
@click.argument('job_id')
def show_job(job_id):
    job = jc.get_job(job_id)

    # job['reverse_dependencies'] = [
    #     x['id'] for x in jc.storage.get_job_revdeps(job['id'])]

    if output_fmt == 'human':
        click.echo('Job id: {0}'.format(job.id))
        click.echo('Title: {0}'.format(job.config['title']))
        click.echo('Function: {0}'.format(job.config['function']))
        click.echo('Args:\n    {0!r}'.format(job.config['args']))
        click.echo('Kwargs:\n    {0!r}'.format(job.config['kwargs']))
        click.echo('Dependencies:')
        for dep in job.get_deps():
            click.echo('    - {0} - {1!r}'.format(dep.id, dep.config['title']))
        click.echo('Reverse dependencies:')
        for dep in job.get_revdeps():
            click.echo('    - {0} - {1!r}'.format(dep.id, dep.config['title']))

        click.echo('')  # Blank line
        click.echo('Status: {0}'.format(job.get_status()))
        lsb = job.get_latest_successful_build()
        click.echo('Latest successful build:')
        if lsb:
            click.echo('    Build id: {0}'.format(lsb.id))
            click.echo('    Started: {0}'.format(lsb['start_time']))
            click.echo('    Finished: {0}'.format(lsb['end_time']))
        else:
            click.echo('    No successful builds')

    elif output_fmt == 'json':
        # todo: dump some information in json
        raise NotImplementedError

    else:
        raise AssertionError('Invalid output format')


@cli_main_grp.command()
def list_jobs():
    jobs = list(jc.iter_jobs())

    if output_fmt == 'human':
        table = PrettyTable(['Id', 'Title'])
        table.align = 'l'
        for item in jobs:
            table.add_row([
                item.config['id'],
                item.config['title'],
                # item.config['function'],
            ])
        click.echo(table)

    elif output_fmt == 'json':
        # todo: serialize datetimes
        click.echo(json_dumps(jobs))

    else:
        raise AssertionError('Invalid output format')


@cli_main_grp.command()
@click.argument('job_id', type=click.STRING)
@click.option('--started/--no-started', default=None)
@click.option('--finished/--no-finished', default=None)
@click.option('--success/--no-success', default=None)
@click.option('--skipped/--no-skipped', default=None)
@click.option('--order', type=click.Choice(('asc', 'desc')), default='desc')
@click.option('--limit', type=click.INT, default=100)
def list_builds(job_id, started, finished, success, skipped, order, limit):
    from jobcontrol.web.template_filters import humanize_timedelta

    job = jc.get_job(job_id)
    builds = job.get_builds(started=started, finished=finished,
                            success=success, skipped=skipped, order=order,
                            limit=limit)

    def _fmt_date(dt):
        if dt is None:
            return 'N/A'
        return dt.strftime('%Y-%m-%d %H:%M:%S')

    def _date_delta(dt1, dt2):
        if dt1 is None or dt2 is None:
            return
        return dt1 - dt2

    if output_fmt == 'human':
        table = PrettyTable(
            ['Build id', 'Status', 'Start time', 'End time', 'Duration',
             'Progress'])

        for item in builds:
            _progress_info = item.get_progress_info()

            table.add_row([
                item.id,
                item.descriptive_status,
                _fmt_date(item['start_time']),
                _fmt_date(item['end_time']),
                humanize_timedelta(
                    _date_delta(item['end_time'], item['start_time'])),
                '{0}/{1} ({2:.0f}%)'.format(
                    _progress_info.current,
                    _progress_info.total,
                    _progress_info.percent * 100),
            ])
        click.echo(table)

    elif output_fmt == 'json':
        click.echo(json_dumps(list(builds)))

    else:
        raise AssertionError('Invalid output format')


@cli_main_grp.command()
@click.argument('build_id', type=click.INT)
def get_build(build_id):
    pass


@cli_main_grp.command()
@click.argument('build_id', type=click.INT)
def delete_build(build_id):
    pass


@cli_main_grp.command()
@click.argument('job_id', type=click.INT)
def build_job(job_id):
    """Run a new build for a job"""

    build_id = jc.build_job(job_id)
    click.echo('Build id: {0}'.format(build_id))


@cli_main_grp.command()
@click.option('--host', help='Server host', default='127.0.0.1')
@click.option('--port', type=click.INT, help='Server port',
              default=5000)
@click.option('--debug/--no-debug',
              help='Whether to enable debug mode (reloader, etc.)',
              default=False)
def web(host, port, debug):
    """Run the web API service"""

    from jobcontrol.web.app import app

    app.config.update(jc.config.webapp)

    server_port = port or app.config.get('PORT') or 5000

    # todo: figure out a better way to pass context..
    # we could use an "application" context -- the flask way..?
    app.config['JOBCONTROL'] = jc

    app.run(port=server_port, debug=debug, host=host)


@cli_main_grp.command()
@click.option('--broker', metavar='URL', help='Broker URL')
def worker(broker):
    """Run the Celery worker"""

    # from jobcontrol.async.tasks import app as celery_app
    import jobcontrol.core  # should set up logging..  # noqa  # nope... :(

    celery_app = jc.get_celery_app()

    # celery_app.conf.JOBCONTROL = jc

    if broker:
        celery_app.conf.BROKER_URL = broker

    # todo: allow passing arguments
    celery_app.worker_main(argv=['jobcontrol-cli'])


@cli_main_grp.command()
@click.argument('job_id', type=click.INT)
@click.option('--broker', metavar='URL', help='Broker URL',
              default='redis://localhost:6379')
def async_build_job(job_id, broker):
    """Run a new build for a job, via Celery"""

    from jobcontrol.async.tasks import app as celery_app, build_job

    celery_app.conf.JOBCONTROL = jc
    celery_app.conf.BROKER_URL = broker

    build_job.delay(job_id)


def main():
    cli_main_grp(obj={})
