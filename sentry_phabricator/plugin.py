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
import json
import phabricator
import sentry_phabricator
import urlparse


class PhabricatorOptionsForm(forms.Form):
    host = forms.URLField(help_text=_("e.g. http://secure.phabricator.org"))
    token = forms.CharField(
        widget=forms.TextInput(attrs={'class': 'span9'}),
        help_text='You may generate a Conduit API Token from your account settings in Phabricator.',
        required=False)
    username = forms.CharField(
        widget=forms.TextInput(attrs={'class': 'span9'}),
        help_text='For token-based authentication you do not need to fill in username.',
        required=False)
    certificate = forms.CharField(
        widget=forms.Textarea(attrs={'class': 'span9'}),
        help_text='For token-based authentication you do not need to fill in certificate.',
        required=False)
    projectPHIDs = forms.CharField(
        widget=forms.Textarea(attrs={'class': 'span9'}),
        help_text='Project PHIDs, use Conduit API /api/project.query to find appropriate values. e.g. ["PHID-PROJ-1", "PHID-PROJ-2"]',
        required=False)

    def clean(self):
        config = self.cleaned_data
        if not config.get('host'):
            raise forms.ValidationError('Missing required host configuration value')
        if not (config.get('token') or (config.get('username') and config.get('certificate'))):
            raise forms.ValidationError('Missing required authentication configuration value')
        projectPHIDs = config.get('projectPHIDs')
        if projectPHIDs:
            try:
                json.loads(projectPHIDs)
            except ValueError:
                raise forms.ValidationError('projectPHIDs field must be a valid JSON if present')
        api = phabricator.Phabricator(
            host=urlparse.urljoin(config['host'], 'api/'),
            username=config['username'],
            certificate=config['certificate'],
            token=config['token'],
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
    author_url = 'https://github.com/getsentry/sentry-phabricator'
    version = sentry_phabricator.VERSION
    description = "Integrate Phabricator issue tracking by linking a user account to a project."
    resource_links = [
        ('Bug Tracker', 'https://github.com/getsentry/sentry-phabricator/issues'),
        ('Source', 'https://github.com/getsentry/sentry-phabricator'),
    ]

    slug = 'phabricator'
    title = _('Phabricator')
    conf_title = 'Phabricator'
    conf_key = 'phabricator'
    project_conf_form = PhabricatorOptionsForm

    def get_api(self, project):
        # check all options are set
        return phabricator.Phabricator(
            host=urlparse.urljoin(self.get_option('host', project), 'api/'),
            username=self.get_option('username', project),
            certificate=self.get_option('certificate', project),
            token=self.get_option('token', project),
        )

    def is_configured(self, project, **kwargs):
        if not self.get_option('host', project):
            return False
        if self.get_option('token', project):
            return True
        if self.get_option('username', project) and self.get_option('certificate', project):
            return True
        return False

    def get_new_issue_title(self, **kwargs):
        return 'Create Maniphest Task'

    def create_issue(self, group, form_data, **kwargs):
        api = self.get_api(group.project)
        try:
            phids = self.get_option('projectPHIDs', group.project)
            if phids:
                phids = json.loads(phids)
            data = api.maniphest.createtask(
                title=form_data['title'].encode('utf-8'),
                description=form_data['description'].encode('utf-8'),
                projectPHIDs=phids,
            )
        except phabricator.APIError, e:
            raise forms.ValidationError('%s %s' % (e.code, e.message))
        except httplib.HTTPException, e:
            raise forms.ValidationError('Unable to reach Phabricator host: %s' % (e.message,))

        return data['id']

    def get_issue_url(self, group, issue_id, **kwargs):
        host = self.get_option('host', group.project)
        return urlparse.urljoin(host, 'T%s' % issue_id)
