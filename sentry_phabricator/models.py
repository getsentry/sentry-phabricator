"""
sentry_phabricator.models
~~~~~~~~~~~~~~~~~~~~~~~~~

:copyright: (c) 2011 by the Sentry Team, see AUTHORS for more details.
:license: BSD, see LICENSE for more details.
"""

from django import forms
from django.core.context_processors import csrf
from django.core.urlresolvers import reverse
from django.utils.safestring import mark_safe

from sentry.models import GroupMeta, ProjectOption
from sentry.plugins import Plugin
from sentry.utils import json

import httplib
import phabricator


class ManiphestTaskForm(forms.Form):
    title = forms.CharField(max_length=200, widget=forms.TextInput(attrs={'class': 'span10'}))
    description = forms.CharField(widget=forms.Textarea(attrs={'class': 'span10'}))
    # assigned_to = forms.CharField()
    # projects = forms.CharField()


class CreateManiphestTask(Plugin):
    title = 'Create Maniphest Task'

    def configure(self, project):
        # check all options are set
        Plugin.configure(self, project)
        config = {}
        for option in ('host', 'certificate', 'username'):
            try:
                value = ProjectOption.objects.get_value(project, 'phabricator:%s' % option)
            except KeyError:
                self.enabled = False
                return
            config[option] = value
        self.config = config
        self.api = phabricator.Phabricator(**config)

    def actions(self, group, action_list, **kwargs):
        if not GroupMeta.objects.get_value(group, 'phabricator:tid', None):
            action_list.append((self.title, self.get_url(group)))
        return action_list

    def _get_group_body(self, group, event, **kwargs):
        interface = event.interfaces.get('sentry.interfaces.Stacktrace')
        if interface:
            return interface.to_string(event)
        return

    def _get_group_description(self, group, event):
        output = [
            'Event:',
            self.request.build_absolute_uri(group.get_absolute_url()),
            '',
            'Details:',
            '```',
            self._get_group_body(group, event),
            '```',
        ]
        return '\n'.join(output)

    def _get_group_title(self, group, event):
        return event.error()

    def view(self, group, **kwargs):
        event = group.get_latest_event()
        form = ManiphestTaskForm(self.request.POST or None, initial={
            'description': self._get_group_description(group, event),
            'title': self._get_group_title(group, event),
        })
        if form.is_valid():
            api = self.api
            try:
                response = api.maniphest.createtask(
                    title=form.cleaned_data['title'],
                    description=form.cleaned_data['description'],
                )
            except phabricator.APIError, e:
                # if e.code == 422:
                #     data = json.loads(e.read())
                #     form.errors['__all__'] = 'Missing or invalid data'
                #     for message in data:
                #         for k, v in message.iteritems():
                #             if k in form.fields:
                #                 form.errors.setdefault(k, []).append(v)
                #             else:
                #                 form.errors['__all__'] += '; %s: %s' % (k, v)
                # else:
                form.errors['__all__'] = 'Bad response from Phabricator: %s %s' % (e.code, e.msg)
            except httplib.HTTPError, e:
                form.errors['__all__'] = 'Unable to reach Phabricator host: %s' % (e.reason,)
            else:
                data = json.loads(response)
                GroupMeta.objects.set_value(group, 'phabricator:tid', data['issue']['id'])
                return self.redirect(reverse('sentry-group', args=[group.project_id, group.pk]))

        context = {
            'form': form,
        }
        context.update(csrf(self.request))

        return self.render('sentry_phabricator/create_maniphest_task.html', context)

    def tags(self, group, tag_list, **kwargs):
        task_id = GroupMeta.objects.get_value(group, 'phabricator:tid', None)
        if task_id:
            tag_list.append(mark_safe('<a href="%s">T%s</a>' % (
                'http://%s/issues/%s' % (self.config['host'], task_id),
                task_id,
            )))
        return tag_list
