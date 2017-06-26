from markupsafe import Markup


NOT_DEPLOYED_STATE_INFOS = ("exclamation-circle", "not-deployed", "Not deployed")
HALF_DEPLOYED_STATE_INFOS = ("warning", "half-deployed", "Deployment outdated")
FULLY_DEPLOYED_STATE_INFOS = ("check", "fully-deployed", "Fully deployed")


def app_modules_state(app):
    icon, state, text = NOT_DEPLOYED_STATE_INFOS
    # If all the modules have been deployed at least once
    if all([bool(module.get('last_deployment', False)) for module in app['modules']]):
        # If all the modules are deployed with the current config
        if all([module['initialized'] for module in app['modules']]):
            icon, state, text = FULLY_DEPLOYED_STATE_INFOS
        else:
            icon, state, text = HALF_DEPLOYED_STATE_INFOS
    return Markup('<span class="fa fa-{icon} state-{state}" title="{text}"></span>'.format(
        icon=icon, state=state, text=text
    ))


def module_state(module):
    icon, state, text = NOT_DEPLOYED_STATE_INFOS
    # If the module has been deployed at least once
    if bool(module.get('last_deployment', False)):
        # If the module is deployed with the current config
        if module['initialized']:
            icon, state, text = FULLY_DEPLOYED_STATE_INFOS
        else:
            icon, state, text = HALF_DEPLOYED_STATE_INFOS
    return Markup('<span class="fa fa-{icon} state-{state}" title="{text}"></span>'.format(
        icon=icon, state=state, text=text
    ))
