import os
from setuptools import setup, find_packages

version = '0.1a'

here = os.path.dirname(__file__)

with open(os.path.join(here, 'README.rst')) as fp:
    longdesc = fp.read()

with open(os.path.join(here, 'CHANGELOG.rst')) as fp:
    longdesc += fp.read()


setup(
    name='jobcontrol',
    version=version,
    packages=find_packages(),
    url='https://github.com/rshk/jobcontrol',
    license='Apache 2.0 License',
    author='Samuele Santi',
    author_email='redshadow@hackzine.org',
    description='Job scheduling and tracking library',
    long_description=longdesc,
    install_requires=['psycopg2'],
    # tests_require=tests_require,
    # test_suite='tests',
    classifiers=[
        'License :: OSI Approved :: Apache Software License',

        'Development Status :: 1 - Planning',
        # 'Development Status :: 2 - Pre-Alpha',
        # 'Development Status :: 3 - Alpha',
        # 'Development Status :: 4 - Beta',
        # 'Development Status :: 5 - Production/Stable',
        # 'Development Status :: 6 - Mature',
        # 'Development Status :: 7 - Inactive',

        # 'Programming Language :: Python :: 2.6',
        'Programming Language :: Python :: 2.7',
    ],
    package_data={'': ['README.rst', 'CHANGELOG.rst']},
    include_package_data=True,
    zip_safe=False)
