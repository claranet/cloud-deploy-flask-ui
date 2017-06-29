from models.apps import apps_schema as ghost_app_schema
from models.env import env as ghost_env_default_values
from models.instance_role import role as ghost_role_default_values

from web_ui.ghost_client import get_ghost_app
from web_ui.ghost_client import get_ghost_job_commands


# Helpers
def empty_fieldlist(fieldlist):
    while len(fieldlist) > 0:
        fieldlist.pop_entry()


def get_wtforms_selectfield_values(allowed_schema_values):
    """
    Returns a list of (value, label) tuples

    >>> get_wtforms_selectfield_values([])
    []
    >>> get_wtforms_selectfield_values(['value'])
    [('value', 'value')]
    >>> get_wtforms_selectfield_values(['value1', 'value2'])
    [('value1', 'value1'), ('value2', 'value2')]
    """
    return [(value, value) for value in allowed_schema_values]


def get_default_name_tag(app):
    """ Return the default configuration for the tag "Name"

        :return dict  The default tag "Name" configuration
    """
    return {
        'tag_name': 'Name',
        'tag_value': 'ec2.{GHOST_APP_ENV}.{GHOST_APP_ROLE}.{GHOST_APP_NAME}'.format(
            GHOST_APP_ENV=app['env'],
            GHOST_APP_ROLE=app['role'],
            GHOST_APP_NAME=app['name'])
    }


def get_ghost_app_envs():
    return get_wtforms_selectfield_values(ghost_env_default_values)


def get_ghost_app_providers():
    return get_wtforms_selectfield_values(ghost_app_schema['provider']['allowed'])


def get_ghost_app_roles():
    return get_wtforms_selectfield_values(ghost_role_default_values)


def get_ghost_mod_scopes():
    return get_wtforms_selectfield_values(ghost_app_schema['modules']['schema']['schema']['scope']['allowed'])


def get_ghost_optional_volumes():
    return get_wtforms_selectfield_values(
        ghost_app_schema['environment_infos']['schema']['optional_volumes']['schema']['schema']['volume_type'][
            'allowed'])


def get_ghost_instance_tags():
    return get_wtforms_selectfield_values(
        ghost_app_schema['environment_infos']['schema']['instance_tags']['schema']['schema']['tag_name']['allowed'])


def get_app_command_recommendations(app_id):
    recommended_cmds = []

    app = get_ghost_app(app_id)
    commands_fields = get_ghost_job_commands(with_fields=True)
    app_modified_fields = app.get('modified_fields', [])

    for cmd in commands_fields:
        cmd_name = cmd[0]
        cmd_fields = cmd[1]
        for field in cmd_fields:
            if field in app_modified_fields:
                recommended_cmds.append({
                    'command': cmd_name,
                    'field': field,
                })
                break

    return recommended_cmds
