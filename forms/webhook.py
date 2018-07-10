from flask_wtf import FlaskForm

from wtforms import HiddenField, RadioField, SubmitField, StringField, FieldList, BooleanField, SelectField
from wtforms.validators import DataRequired
from web_ui.forms.form_helper import empty_fieldlist
from web_ui.forms.form_wtf_helper import BetterSelectField
from web_ui.forms.form_aws_helper import get_aws_ec2_instance_types


from command import DeployModuleForm, CommandAppForm


class BaseWebhookForm(FlaskForm):
    app_id = BetterSelectField('Application ID', validators=[DataRequired()])
    module = BetterSelectField('Module name', validators=[DataRequired()])
    rev = StringField('Revision regex', validators=[DataRequired()])
    secret_token = StringField('Secret token')
    events = FieldList(BetterSelectField('Trigger events',
                                         choices=[('push', 'push'), ('tag', 'tag'), ('merge', 'merge')]), min_entries=1)
    command = BetterSelectField('Command to run',
                                choices=[('deploy', 'deploy'), ('buildimage', 'buildimage')], default='deploy',
                                validators=[DataRequired()])
    fabric_execution_strategy = BetterSelectField('Deployment strategy', validators=[],
                                                  choices=[('serial', 'serial'), ('parallel', 'parallel')])
    safe_deployment = BooleanField('Deploy with Safe Deployment')
    safe_deployment_strategy = SelectField('Safe Deployment Strategy', default='')
    instance_type = SelectField('Instance Type')

    def map_from_webhook(self, webhook):
        """
        Map webhook data to form
        """
        self.app_id.data = webhook.get('app_id', '')
        self.module.data = webhook.get('module', '')
        self.rev.data = webhook.get('rev', '')
        self.secret_token.data = webhook.get('secret_token', '')

        if len(webhook.get('events', [])) > 0:
            empty_fieldlist(self.events)
            for event in webhook.get('events', []):
                self.events.append_entry(event)

        if len(webhook.get('commands', [])) > 0:
            for command in webhook.get('commands', []):
                self.command.data = command

        if 'options' in webhook:
            self.fabric_execution_strategy.data = webhook['options'].get('fabric_execution_strategy', '')
            self.safe_deployment_strategy.data = webhook['options'].get('safe_deployment_strategy', '')
            self.instance_type.data = webhook['options'].get('instance_type', '')

    def map_to_webhook(self, webhook):
        """
        Map webhook data from form to webhook
        """
        webhook['app_id'] = self.app_id.data
        webhook['module'] = self.module.data
        webhook['rev'] = self.rev.data
        webhook['secret_token'] = self.secret_token.data
        webhook['commands'] = [self.command.data]
        webhook['events'] = []
        for event in self.events:
            if event.data:
                webhook['events'].append(event.data)

        # Add command options
        webhook['options'] = {
            'fabric_execution_strategy': None,
            'safe_deployment_strategy': None,
            'instance_type': None
        }
        if self.command.data == 'deploy':
            webhook['options']['fabric_execution_strategy'] = self.fabric_execution_strategy.data
            webhook['options']['safe_deployment_strategy'] = self.safe_deployment_strategy.data
        if self.command.data == 'buildimage':
            webhook['options']['instance_type'] = self.instance_type.data or None


class CreateWebhookForm(BaseWebhookForm):
    submit = SubmitField('Create Webhook')

    def __init__(self, *args, **kwargs):
        super(CreateWebhookForm, self).__init__(*args, **kwargs)

        # Set available choices
        self.command.choices = [('deploy', 'deploy'), ('buildimage', 'buildimage')]
        self.fabric_execution_strategy.choices = [('serial', 'serial'), ('parallel', 'parallel')]
        for event in self.events:
            event.choices = [('push', 'push'), ('tag', 'tag'), ('merge', 'merge')]
        self.module.choices = [('', 'Please select app first')]
        self.safe_deployment_strategy.choices = [('', '-- Computing available strategies --')]
        self.instance_type.choices = [('', '-- Computing available instances --')]


class EditWebhookForm(BaseWebhookForm):
    submit = SubmitField('Update Webhook')
    etag = HiddenField(validators=[DataRequired()])

    app_id_ro = StringField('Webhook app', description='This field is not editable')
    module_ro = StringField('Module name', description='This field is not editable')

    def __init__(self, *args, **kwargs):
        super(EditWebhookForm, self).__init__(*args, **kwargs)

        # Set available choices
        self.command.choices = [('deploy', 'deploy'), ('buildimage', 'buildimage')]
        self.fabric_execution_strategy.choices = [('serial', 'serial'), ('parallel', 'parallel')]
        self.safe_deployment_strategy.choices = [('', '-- Computing available strategies --')]
        self.instance_type.choices = [('', '-- Computing available instances --')]
        for event in self.events:
            event.choices = [('push', 'push'), ('tag', 'tag'), ('merge', 'merge')]

    def map_from_webhook(self, webhook):
        super(EditWebhookForm, self).map_from_webhook(webhook)

        if not self.app_id.data:
            self.app_id_ro.data = 'Invalid app. Webhook must be removed.'
        else:
            self.app_id_ro.data = '{name} ({id})'.format(name=self.app_id.data['name'], id=self.app_id.data['_id'])
        self.module_ro.data = self.module.data

        self.etag.data = webhook.get('_etag', '')


class DeleteWebhookForm(FlaskForm):
    etag = HiddenField(validators=[DataRequired()])
    confirmation = RadioField('Are you sure?', validators=[DataRequired()],
                              choices=[('yes', 'Yes'), ('no', 'No')])

    submit = SubmitField('Delete Webhook')

