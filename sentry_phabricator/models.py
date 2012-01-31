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

import httplib
import phabricator
import urlparse


class ManiphestTaskForm(forms.Form):
    title = forms.CharField(max_length=200, widget=forms.TextInput(attrs={'class': 'span9'}))
    description = forms.CharField(widget=forms.Textarea(attrs={'class': 'span9'}))
    # assigned_to = forms.CharField()
    # projects = forms.CharField()


class PhabricatorOptionsForm(forms.Form):
    host = forms.URLField(help_text="e.g. http://secure.phabricator.org")
    username = forms.CharField(widget=forms.TextInput(attrs={'class': 'span9'}))
    certificate = forms.CharField(widget=forms.Textarea(attrs={'class': 'span9'}))

    def clean(self):
        config = self.cleaned_data
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


class CreateManiphestTask(Plugin):
    title = 'Phabricator'
    conf_title = 'Phabricator'
    conf_key = 'phabricator'
    project_conf_form = PhabricatorOptionsForm

    def __init__(self, *args, **kwargs):
        super(CreateManiphestTask, self).__init__(*args, **kwargs)
        self._cache = {}
        self._config = {}

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
        return bool(self.get_config(project))

    def get_config(self, project):
        if project.pk not in self._config:
            prefix = self.get_conf_key()
            config = {}
            for option in ('host', 'certificate', 'username'):
                try:
                    value = ProjectOption.objects.get_value(project, '%s:%s' % (prefix, option))
                except KeyError:
                    return {}
                config[option] = value
            self._config[project.pk] = config
        return self._config[project.pk]

    def get_api(self, project):
        # check all options are set
        config = self.get_config(project)
        return phabricator.Phabricator(
            host=urlparse.urljoin(config['host'], 'api/'),
            username=config['username'],
            certificate=config['certificate'],
        )

    def actions(self, request, group, action_list, **kwargs):
        prefix = self.get_conf_key()
        if not GroupMeta.objects.get_value(group, '%s:tid' % prefix, None):
            action_list.append(('Create Maniphest Task', self.get_url(group)))
        return action_list

    def view(self, request, group, **kwargs):
        if not self.is_configured(group.project):
            return self.render('sentry_phabricator/not_configured.html')

        prefix = self.get_conf_key()
        event = group.get_latest_event()
        form = ManiphestTaskForm(request.POST or None, initial={
            'description': self._get_group_description(request, group, event),
            'title': self._get_group_title(request, group, event),
        })
        if form.is_valid():
            api = self.get_api(group.project)
            try:
                data = api.maniphest.createtask(
                    title=form.cleaned_data['title'].encode('utf-8'),
                    description=form.cleaned_data['description'].encode('utf-8'),
                )
            except phabricator.APIError, e:
                form.errors['__all__'] = '%s %s' % (e.code, e.message)
            except httplib.HTTPException, e:
                form.errors['__all__'] = 'Unable to reach Phabricator host: %s' % (e.reason,)
            else:
                GroupMeta.objects.set_value(group, '%s:tid' % prefix, data['id'])
                return self.redirect(reverse('sentry-group', args=[group.project_id, group.pk]))

        context = {
            'form': form,
        }
        context.update(csrf(request))

        return self.render('sentry_phabricator/create_maniphest_task.html', context)

    def before_events(self, request, event_list, **kwargs):
        prefix = self.get_conf_key()
        self._cache = GroupMeta.objects.get_value_bulk(event_list, '%s:tid' % prefix)

    def tags(self, request, group, tag_list, **kwargs):
        try:
            host = self.get_config(group.project)['host']
        except KeyError:
            return
        task_id = self._cache.get(group.pk)
        if task_id:
            tag_list.append(mark_safe('<a href="%s">T%s</a>' % (
                urlparse.urljoin(host, 'T%s' % task_id),
                task_id,
            )))
        return tag_list
