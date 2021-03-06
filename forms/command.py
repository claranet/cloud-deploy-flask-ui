from flask_wtf import FlaskForm
from wtforms import FieldList, FormField, HiddenField, SelectField, StringField, SubmitField, TextAreaField, BooleanField
from wtforms.validators import DataRequired as DataRequiredValidator
from wtforms.validators import Regexp as RegexpValidator

from web_ui.forms.form_wtf_helper import BetterSelectField, BetterSelectFieldNonValidating
from web_ui.forms.form_helper import empty_fieldlist
from web_ui.forms.form_aws_helper import get_aws_ec2_instance_types
from web_ui.ghost_client import get_ghost_app, get_ghost_job_commands


class DeployModuleForm(FlaskForm):
    name = HiddenField('')
    deploy = BooleanField('', validators=[])
    rev = StringField('Revision', validators=[])
    available_revisions = BetterSelectFieldNonValidating('Available revisions', validators=[],
                                                         choices=[('', '-- Retrieving available revisions --')])

    # Disable CSRF in module forms as they are subforms
    def __init__(self, csrf_enabled=False, *args, **kwargs):
        super(DeployModuleForm, self).__init__(meta={'csrf': False}, *args, **kwargs)

    def map_from_app(self, module):
        self.name.data = module.get('name', '')
        self.deploy.label.text = module.get('name', '')


class CommandAppForm(FlaskForm):
    command = BetterSelectField('Command', validators=[DataRequiredValidator()], choices=[])
    modules = FieldList(FormField(DeployModuleForm), min_entries=1)
    deploy_id = StringField('Deploy ID', validators=[])
    fabric_execution_strategy = BetterSelectField('Deployment strategy', validators=[],
                                                  choices=[('serial', 'serial'), ('parallel', 'parallel')])
    safe_deployment = BooleanField('Deploy with Safe Deployment', validators=[])
    safe_deployment_strategy = SelectField('Safe Deployment Strategy', validators=[], choices=[])
    rolling_update = BooleanField('Use Rolling Update strategy', validators=[])
    rolling_update_strategy = SelectField('Rolling Update strategy', validators=[], choices=[])
    swapbluegreen_strategy = SelectField('Blue Green Swap Strategy', validators=[], choices=[
        ('overlap',  'Overlap --- Blue/Green without downtime but two versions could be in production at the same time.'),
        ('isolated', 'Isolated --- Blue/Green with a downtime but ensures that only one version is in production.')])
    instance_type = BetterSelectField('Instance Type', validators=[], choices=[])
    skip_provisioner_bootstrap = BooleanField('Skip Provisioner Bootstrap', validators=[])
    private_ip_address = StringField('Private IP address', validators=[
        RegexpValidator("^$|^([0-9]{1,3})\.([0-9]{1,3})\.([0-9]{1,3})\.([0-9]{1,3})$")])
    subnet = BetterSelectField('Subnet', validators=[], choices=[])
    prepare_bg_copy_ami = BooleanField('Copy AMI from online app', validators=[])
    prepare_create_temp_elb = BooleanField('Create a temporary ELB to attach to the Auto Scaling goup', validators=[])
    to_execute_script = TextAreaField('Script to execute', description='Script executed on every instance.',
                                      validators=[])
    script_module_context = BetterSelectFieldNonValidating('Module context', validators=[],
                                                           choices=[('', '-- No module context --')])

    execution_strategy = BetterSelectField('Execution strategy', validators=[], choices=[
        ('single', 'On a single host'),
        ('serial', 'On every host in *serial*'),
        ('parallel', 'On every host in *parallel*')])
    single_host_instance = BetterSelectFieldNonValidating('Instance private IP', validators=[],
                                                          choices=[('', '-- Retrieving available instances --')])

    submit = SubmitField('Run Application Command')

    def __init__(self, app_id, *args, **kwargs):
        super(CommandAppForm, self).__init__(*args, **kwargs)

        # Get the Ghost application
        app = get_ghost_app(app_id)

        # Get the list of commands at construction time because it requires a request context
        self.command.choices = get_ghost_job_commands(app_id=app_id)

        # Get the instance types in the Ghost application's region
        self.instance_type.choices = get_aws_ec2_instance_types(app["region"])

        # Get the safe deployment possibilities
        self.safe_deployment_strategy.choices = [('', '-- Computing available strategies --')]

        # Get the safe destroy possibilities
        self.rolling_update_strategy.choices = [('', '-- Computing available strategies --')]

        # Get the subnets of the current application
        self.subnet.choices = [('', '-- Retrieving available subnets... --')]

    def map_from_app(self, app):
        """
        Map app data from app to form
        """
        # Use the instance type of the Ghost application as default
        self.instance_type.data = app.get('instance_type', '')
        self.map_from_app_modules(app)

    def map_from_app_modules(self, app):
        """
        Map modules data from app to form
        """
        self.script_module_context.choices = [('', '-- No module context --')]
        if 'modules' in app and len(app['modules']) > 0:
            empty_fieldlist(self.modules)
            for module in app.get('modules', []):
                self.modules.append_entry()
                form_module = self.modules.entries[-1].form
                form_module.map_from_app(module)
                self.script_module_context.choices.append((module.get('name', ''), module.get('name', '')))
