sentry-phabricator
==================

An extension for Sentry which integrates with Phabricator. Specifically, it allows you to easily create
Maniphest tasks from events within Sentry.


Install
-------

Install the package via ``pip``::

    pip install sentry-phabricator

Configuration
-------------

Create a user within your Phabricator install (a system agent). This user will
be creating tickets on your behalf via Sentry.

Go to your project's configuration page (Projects -> [Project]) and select the
Phabricator tab. Enter the required credentials and click save changes.

You'll now see a new action on groups which allows quick creation of Maniphest
tasks.