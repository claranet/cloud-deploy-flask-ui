from flask import Markup


NOT_DEPLOYED_STATE_INFOS = ("exclamation-circle", "not-deployed", "Not deployed")
HALF_DEPLOYED_STATE_INFOS = ("warning", "half-deployed", "Deployment outdated")
FULLY_DEPLOYED_STATE_INFOS = ("check", "fully-deployed", "Fully deployed")


def app_modules_state(app):
    """
    Outputs an html snippet with icon and tooltip that indicates the app deployment status
    :param app: dict: a ghost applicatiob
    :return: str: the html snippet
    """
    icon, state, text = NOT_DEPLOYED_STATE_INFOS
    # If all the modules have been deployed at least once
    if all([bool(module.get('last_deployment', False)) for module in app['modules']]):
        # If all the modules are deployed with the current config
        if all([module['initialized'] for module in app['modules']]):
            icon, state, text = FULLY_DEPLOYED_STATE_INFOS
        else:
            icon, state, text = HALF_DEPLOYED_STATE_INFOS
    return Markup('<span class="fa fa-{icon} state-{state}" title="{text}" data-toggle="tooltip"></span>'.format(
        icon=icon, state=state, text=text
    ))


def module_state(module):
    """
    Outputs an html snippet with icon and tooltip that indicates the module deployment status
    :param module: dict: a ghost module
    :return: str: the html snippet
    """
    icon, state, text = NOT_DEPLOYED_STATE_INFOS
    # If the module has been deployed at least once
    if bool(module.get('last_deployment', False)):
        # If the module is deployed with the current config
        if module['initialized']:
            icon, state, text = FULLY_DEPLOYED_STATE_INFOS
        else:
            icon, state, text = HALF_DEPLOYED_STATE_INFOS
    return Markup('<span class="fa fa-{icon} state-{state}" title="{text}" data-toggle="tooltip"></span>'.format(
        icon=icon, state=state, text=text
    ))


def check_status_code(code):
    """
    Checks if the code is HTTP OK
    :param code:
    :return:
    """
    return code and code in [200, 201, 204]
