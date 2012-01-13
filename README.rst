sentry-phabricator
==================

An extension for Sentry which integrates with Phabricator. Specifically, it allows you to easily create
Maniphest tickets from events within Sentry.


Install
-------

Install the package via ``pip``::

    pip install sentry-phabricator

Add ``sentry_phabricator`` to your ``INSTALLED_APPS``::

    INSTALLED_APPS = (
        # ...
        'sentry',
        'sentry_phabricator',
    )

Configuration
-------------

Go to your project's configuration page (Projects -> [Project]) and select the
Phabricator tab. Enter the required credentials and click save changes.

You'll now see a new action on groups which allows quick creation of Maniphest
Tickets.