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
    title = forms.CharField(max_length=200, widget=forms.TextInput(attrs={'class': 'span10'}))
    description = forms.CharField(widget=forms.Textarea(attrs={'class': 'span10'}))
    # assigned_to = forms.CharField()
    # projects = forms.CharField()


class PhabricatorOptionsForm(forms.Form):
    host = forms.URLField(help_text="e.g. http://secure.phabricator.org")
    username = forms.CharField(widget=forms.TextInput(attrs={'class': 'span10'}))
    certificate = forms.CharField(widget=forms.Textarea(attrs={'class': 'span10'}))

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
            raise forms.ValidationError('Unable to reach Phabricator host: %s' % (e.reason,))
        except Exception, e:
            raise forms.ValidationError('Unhandled error from Phabricator: %s' % (e,))


class CreateManiphestTask(Plugin):
    title = 'Phabricator'
    conf_title = 'Phabricator'
    conf_key = 'phabricator'
    project_conf_form = PhabricatorOptionsForm

    def configure(self, project):
        # check all options are set
        self._cache = {}
        prefix = self.get_conf_key()
        Plugin.configure(self, project)
        config = {}
        for option in ('host', 'certificate', 'username'):
            try:
                value = ProjectOption.objects.get_value(project, '%s:%s' % (prefix, option))
            except KeyError:
                self.enabled = False
                return
            config[option] = value
        self.config = config
        self.api = phabricator.Phabricator(
            host=urlparse.urljoin(config['host'], 'api/'),
            username=config['username'],
            certificate=config['certificate'],
        )

    def actions(self, group, action_list, **kwargs):
        prefix = self.get_conf_key()
        if not GroupMeta.objects.get_value(group, '%s:tid' % prefix, None):
            action_list.append(('Create Maniphest Task', self.get_url(group)))
        return action_list

    def _get_group_body(self, group, event, **kwargs):
        interface = event.interfaces.get('sentry.interfaces.Stacktrace')
        if interface:
            return interface.to_string(event)
        return

    def _get_group_description(self, group, event):
        output = [
            self.request.build_absolute_uri(group.get_absolute_url()),
            '',
            '```',
            self._get_group_body(group, event),
            '```',
        ]
        return '\n'.join(output)

    def _get_group_title(self, group, event):
        return event.error()

    def view(self, group, **kwargs):
        prefix = self.get_conf_key()
        event = group.get_latest_event()
        form = ManiphestTaskForm(self.request.POST or None, initial={
            'description': self._get_group_description(group, event),
            'title': self._get_group_title(group, event),
        })
        if form.is_valid():
            api = self.api
            try:
                data = api.maniphest.createtask(
                    title=form.cleaned_data['title'],
                    description=form.cleaned_data['description'],
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
        context.update(csrf(self.request))

        return self.render('sentry_phabricator/create_maniphest_task.html', context)

    def before_events(self, event_list, **kwargs):
        prefix = self.get_conf_key()
        self._cache = GroupMeta.objects.get_value_bulk(event_list, '%s:tid' % prefix)

    def tags(self, group, tag_list, **kwargs):
        task_id = self._cache.get(group.pk)
        if task_id:
            tag_list.append(mark_safe('<a href="%s">T%s</a>' % (
                urlparse.urljoin(self.config['host'], 'T%s' % task_id),
                task_id,
            )))
        return tag_list
