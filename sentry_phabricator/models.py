"""
sentry_phabricator
~~~~~~~~~~~~~~~~~~

:copyright: (c) 2010 by the Sentry Team, see AUTHORS for more details.
:license: BSD, see LICENSE for more details.
"""

from django import forms
from django.core.context_processors import csrf
from django.core.urlresolvers import reverse
from django.http import HttpResponseRedirect
from django.shortcuts import render_to_response
from django.utils.safestring import mark_safe

from sentry.models import GroupMeta, ProjectOption
from sentry.plugins import GroupActionProvider
from sentry.plugins.sentry_redmine import conf
from sentry.utils import json

import phabricator
import urllib2


class ManiphestTaskForm(forms.Form):
    title = forms.CharField(max_length=200)
    assigned_to = forms.CharField()
    projects = forms.CharField()
    description = forms.CharField(widget=forms.Textarea())


class CreateManiphestTask(GroupActionProvider):
    title = 'Create Maniphest Task'

    def configure(self, project):
        # check all options are set
        config = {}
        for option in ('host', 'certificate', 'username'):
            try:
                value = ProjectOption.objects.get_value(project, 'phabricator:%s' % option)
            except KeyError:
                self.enabled = False
                return
            config[option] = value
        self.enabled = True
        self.config = config
        self.api = phabricator.Phabricator(**config)
        # api.user.whoami().userName

    def actions(self, request, action_list, project, group):
        if not GroupMeta.objects.get_value(group, 'phabricator:tid', None):
            action_list.append((self.title, self.__class__.get_url(project.pk, group.pk)))
        return action_list

    def view(self, request, group):
        form = ManiphestTaskForm(request.POST or None, initial={
            'description': 'Sentry Message: %s\n\n<pre>%s</pre>' % (
                request.build_absolute_uri(group.get_absolute_url()),
                group.message,
            ),
            'title': group.error(),
        })
        if form.is_valid():
            # data = json.dumps({
            #     'key': conf.REDMINE_API_KEY,
            #     'issue': {
            #         'subject': form.cleaned_data['subject'],
            #         'description': form.cleaned_data['description'],
            #     }
            # })
            # url = conf.REDMINE_URL + '/projects/' + conf.REDMINE_PROJECT_SLUG + '/issues.json'

            # req = urllib2.Request(url, urllib.urlencode({
            #     'key': conf.REDMINE_API_KEY,
            # }), headers={
            #     'Content-type': 'application/json',
            # })
            try:
                response = urllib2.urlopen(req, data).read()
            except urllib2.HTTPError, e:
                if e.code == 422:
                    data = json.loads(e.read())
                    form.errors['__all__'] = 'Missing or invalid data'
                    for message in data:
                        for k, v in message.iteritems():
                            if k in form.fields:
                                form.errors.setdefault(k, []).append(v)
                            else:
                                form.errors['__all__'] += '; %s: %s' % (k, v)
                else:
                    form.errors['__all__'] = 'Bad response from Redmine: %s %s' % (e.code, e.msg)
            except urllib2.URLError, e:
                form.errors['__all__'] = 'Unable to reach Redmine host: %s' % (e.reason,)
            else:
                data = json.loads(response)
                GroupMeta.objects.set_value(group, 'phabricator:tid', data['issue']['id'])
                return HttpResponseRedirect(reverse('sentry-group', args=[group.project_id, group.pk]))

        context = {
            'request': request,
            'group': group,
            'form': form,
            'global_errors': form.errors.get('__all__'),
            'BASE_TEMPLATE': 'sentry/groups/details.html',
        }
        context.update(csrf(request))

        return render_to_response('sentry_phabricator/create_maniphest_task.html', context)

    def tags(self, request, tags, project, group):
        task_id = GroupMeta.objects.get_value(group, 'phabricator:tid', None)
        if task_id:
            tags.append(mark_safe('<a href="%s">#%s</a>' % (
                '%s/issues/%s' % (conf.PHABRICATOR_URL, task_id),
                task_id,
            )))
        return tags
