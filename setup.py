#!/usr/bin/env python
"""
sentry-phabricator
==================

An extension for Sentry which integrates with Phabricator. Specifically, it allows you to easily create
Maniphest tasks from events within Sentry.

:copyright: (c) 2011 by the Sentry Team, see AUTHORS for more details.
:license: BSD, see LICENSE for more details.
"""
from setuptools import setup, find_packages


tests_require = [
    'nose==1.1.2',
]

install_requires = [
    'sentry>=2.1.0',
    'python-phabricator',
    # https://github.com/disqus/python-phabricator/zipball/master
]

setup(
    name='sentry-phabricator',
    version='0.4.0',
    author='David Cramer',
    author_email='dcramer@gmail.com',
    url='http://github.com/dcramer/sentry-phabricator',
    description='A Sentry extension which integrates with Phabricator.',
    long_description=__doc__,
    license='BSD',
    packages=find_packages(exclude=['tests']),
    zip_safe=False,
    install_requires=install_requires,
    tests_require=tests_require,
    extras_require={'test': tests_require},
    test_suite='runtests.runtests',
    include_package_data=True,
    classifiers=[
        'Framework :: Django',
        'Intended Audience :: Developers',
        'Intended Audience :: System Administrators',
        'Operating System :: OS Independent',
        'Topic :: Software Development'
    ],
)
