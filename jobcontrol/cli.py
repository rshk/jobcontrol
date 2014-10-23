import ast

import click
from flask.config import Config
from prettytable import PrettyTable

from jobcontrol.core import JobControl
from jobcontrol.utils import (
    get_storage_from_url, get_storage_from_config, short_repr,
    json_dumps)


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


@click.group()
@click.option('--config-file', metavar='FILE',
              help='Path to configuration file')
@click.option('--storage', metavar='FILE', help='Storage URL')
@click.option('--format', default='human',
              help='Output format. "human" or "json" (default: "human").',
              type=click.Choice(('json', 'human')))
def cli_main_grp(config_file, storage, format):

    global jc, config, output_fmt

    output_fmt = format

    config = Config(__name__)
    if config_file is not None:
        config.from_pyfile(config_file)

    if storage:
        storage_obj = get_storage_from_url(storage)

    else:
        storage_obj = get_storage_from_config(config)

    jc = JobControl(storage_obj)


@cli_main_grp.command()
def install():
    jc.storage.install()


@cli_main_grp.command()
def uninstall():
    jc.storage.uninstall()


@cli_main_grp.command()
@click.option('--function', help="Function to be called", required=True)
@click.option('--args', help="Arguments, as a Python tuple")
@click.option('--kwargs', help="Keyword arguments, as a Python dict")
@click.option('--dependencies', help="Comma-separated list of job ids")
def create_job(function, args, kwargs, dependencies):
    args = ast.literal_eval(args) if args else ()
    kwargs = ast.literal_eval(kwargs) if kwargs else {}
    if dependencies:
        dependencies = [int(x) for x in dependencies.split(',')]
    else:
        dependencies = []

    retval = jc.storage.create_job(function, args=args, kwargs=kwargs,
                                   dependencies=dependencies)

    if output_fmt == 'human':
        click.echo('Job id: {0}'.format(retval))

    elif output_fmt == 'json':
        click.echo(json_dumps({'id': retval}))

    else:
        raise AssertionError('Invalid output format')


@cli_main_grp.command()
@click.argument('job_id', type=click.INT)
@click.option('--function', help="Function to be called")
@click.option('--args', help="Arguments, as a Python tuple")
@click.option('--kwargs', help="Keyword arguments, as a Python dict")
@click.option('--dependencies', help="Comma-separated list of job ids")
def update_job(job_id, function, args, kwargs, dependencies):
    kwargs = {}

    if function is not None:
        kwargs['function'] = function

    if args is not None:
        kwargs['args'] = ast.literal_eval(args)

    if kwargs is not None:
        kwargs['kwargs'] = ast.literal_eval(kwargs)

    if dependencies is not None:
        kwargs['dependencies'] = [int(x) for x in dependencies.split(',')]

    jc.storage.update_job(job_id, **kwargs)


@cli_main_grp.command()
@click.argument('job_id', type=click.INT)
def get_job(job_id):
    job = jc.storage.get_job(job_id)

    job['reverse_dependencies'] = [
        x['id'] for x in jc.storage.get_job_revdeps(job['id'])]

    if output_fmt == 'human':
        table = PrettyTable(['Key', 'Value'])
        table.align.update({'Key': 'r', 'Value': 'l'})
        table.add_row(("Job id:", job['id']))
        table.add_row(("Created:", _fmt_date(job['ctime'])))
        table.add_row(("Updated:", _fmt_date(job['mtime'])))
        table.add_row(("Function:", job['function']))
        table.add_row(("args:", job['args']))
        table.add_row(("kwargs:", job['kwargs']))
        table.add_row(("Deps:", job['dependencies']))
        table.add_row(("Rev. deps:", job['reverse_dependencies']))
        click.echo(table)

    elif output_fmt == 'json':
        click.echo(json_dumps(job))

    else:
        raise AssertionError('Invalid output format')


@cli_main_grp.command()
@click.argument('job_id', type=click.INT)
def delete_job(job_id):
    jc.storage.delete_job(job_id)


@cli_main_grp.command()
def list_jobs():
    jobs = list(jc.storage.iter_jobs())

    if output_fmt == 'human':
        table = PrettyTable(
            ['Id', 'Ctime', 'Function', 'Args', 'Kwargs', 'Deps'])
        for item in jobs:
            table.add_row([
                item['id'],
                item['ctime'].strftime('%Y-%m-%d %H:%M'),
                item['function'],
                short_repr(item['args'], 40),
                short_repr(item['kwargs'], 40),
                item['dependencies'],
            ])
        click.echo(table)

    elif output_fmt == 'json':
        # todo: serialize datetimes
        click.echo(json_dumps(jobs))

    else:
        raise AssertionError('Invalid output format')


@cli_main_grp.command()
@click.argument('job_id', type=click.INT)
@click.option('--started', type=click.BOOL)
@click.option('--finished', type=click.BOOL)
@click.option('--success', type=click.BOOL)
@click.option('--skipped', type=click.BOOL)
@click.option('--order', type=click.Choice(('asc', 'desc')), default='asc')
@click.option('--limit', type=click.INT, default=100)
def list_builds(job_id, started, finished, success, skipped, order, limit):
    builds = jc.storage.get_job_builds(
        job_id, started=started, finished=finished, success=success,
        skipped=skipped, order=order, limit=limit)

    if output_fmt == 'human':
        table = PrettyTable(
            ['Job id', 'Build id', 'Start time', 'End time', 'Started',
             'Finished', 'Success', 'Skipped', 'Progress', 'Return value',
             'Exception'])

        for item in builds:
            table.add_row([
                item['job_id'],
                item['id'],

                item['start_time'],
                item['end_time'],
                item['started'],
                item['finished'],
                item['success'],
                item['skipped'],
                '{0}/{1}'.format(item['progress_current'],
                                 item['progress_total']),
                item['retval'],
                item['exception'],
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


def main():
    cli_main_grp(obj={})
