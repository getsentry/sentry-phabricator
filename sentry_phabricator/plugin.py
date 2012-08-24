"""
sentry_phabricator.plugin
~~~~~~~~~~~~~~~~~~~~~~~~~

:copyright: (c) 2011 by the Sentry Team, see AUTHORS for more details.
:license: BSD, see LICENSE for more details.
"""

from django import forms
from django.utils.translation import ugettext_lazy as _

from sentry.plugins.bases.issue import IssuePlugin

import httplib
import phabricator
import sentry_phabricator
import urlparse


class PhabricatorOptionsForm(forms.Form):
    host = forms.URLField(help_text=_("e.g. http://secure.phabricator.org"))
    username = forms.CharField(widget=forms.TextInput(attrs={'class': 'span9'}))
    certificate = forms.CharField(widget=forms.Textarea(attrs={'class': 'span9'}))

    def clean(self):
        config = self.cleaned_data
        if not all(config.get(k) for k in ('host', 'username', 'certificate')):
            raise forms.ValidationError('Missing required configuration value')
        api = phabricator.Phabricator(
            host=urlparse.urljoin(config['host'], 'api/'),
            username=config['username'],
            certificate=config['certificate'],
        )
        try:
            api.user.whoami()
        except phabricator.APIError, e:
            raise forms.ValidationError('%s %s' % (e.code, e.message))
        except httplib.HTTPException, e:
            raise forms.ValidationError('Unable to reach Phabricator host: %s' % (e,))
        except Exception, e:
            raise forms.ValidationError('Unhandled error from Phabricator: %s' % (e,))
        return config


class PhabricatorPlugin(IssuePlugin):
    author = 'DISQUS'
    author_url = 'https://github.com/disqus/sentry-phabricator'
    version = sentry_phabricator.VERSION

    slug = 'phabricator'
    title = _('Phabricator')
    conf_title = 'Phabricator'
    conf_key = 'phabricator'
    project_conf_form = PhabricatorOptionsForm

    def __init__(self, *args, **kwargs):
        super(PhabricatorPlugin, self).__init__(*args, **kwargs)
        self._cache = {}

    def _get_group_body(self, request, group, event, **kwargs):
        interface = event.interfaces.get('sentry.interfaces.Stacktrace')
        if interface:
            return interface.to_string(event)
        return

    def _get_group_description(self, request, group, event):
        output = [
            request.build_absolute_uri(group.get_absolute_url()),
        ]
        body = self._get_group_body(request, group, event)
        if body:
            output.extend([
                '',
                '```',
                body,
                '```',
            ])
        return '\n'.join(output)

    def _get_group_title(self, request, group, event):
        return event.error()

    def is_configured(self, project):
        return all((self.get_option(k, project) for k in ('host', 'username', 'certificate')))

    def get_api(self, project):
        # check all options are set
        return phabricator.Phabricator(
            host=urlparse.urljoin(self.get_option('host', project), 'api/'),
            username=self.get_option('username', project),
            certificate=self.get_option('certificate', project),
        )

    def get_new_issue_title(self):
        return 'Create Maniphest Task'

    def create_issue(self, group, form_data):
        api = self.get_api(group.project)
        try:
            data = api.maniphest.createtask(
                title=form_data['title'].encode('utf-8'),
                description=form_data['description'].encode('utf-8'),
            )
        except phabricator.APIError, e:
            raise forms.ValidationError('%s %s' % (e.code, e.message))
        except httplib.HTTPException, e:
            raise forms.ValidationError('Unable to reach Phabricator host: %s' % (e.reason,))

        return data['id']

    def get_issue_url(self, group, issue_id):
        host = self.get_option('host', group.project)
        return urlparse.urljoin(host, 'T%s' % issue_id)
