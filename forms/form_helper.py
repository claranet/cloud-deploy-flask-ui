from models.apps import apps_schema as ghost_app_schema
from models.env import env as ghost_env_default_values
from models.instance_role import role as ghost_role_default_values


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
