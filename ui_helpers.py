from markupsafe import Markup


def app_modules_state(app):
    icon, state, text = ("exclamation-circle", "not-deployed", "Not deployed")
    # If all the modules have been deployed at least once
    if all([bool(module.get('last_deployment', False)) for module in app['modules']]):
        # If all the modules are deployed with the current config
        if all([module['initialized'] for module in app['modules']]):
            icon, state, text = ("check", "fully-deployed", "Fully deployed")
        else:
            icon, state, text = ("warning", "half-deployed", "Deployment outdated")
    return Markup('<span class="fa fa-{icon} state-{state}" title="{text}"></span>'.format(
        icon=icon, state=state, text=text
    ))
