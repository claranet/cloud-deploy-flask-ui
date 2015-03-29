from flask import Flask, render_template, request, make_response
from flask_bootstrap import Bootstrap
import aws_data
import instance_role
import env
import base64
import tempfile
import os
import requests
import json

# FIXME: Static conf to externalize with Flask-Appconfig
auth = ('api', 'api')
headers = {'Content-type': 'application/json', 'Accept': 'text/plain'}
url_apps = 'http://localhost:5000/apps'
url_jobs = 'http://localhost:5000/jobs'


# Helpers
def get_ghost_apps():
    try:
        apps = requests.get(url_apps, headers=headers, auth=auth).json()['_items']
    except:
        apps = ['Failed to retrieve Apps']

    return apps

# FIXME: Get list from AWS API
def get_vpc():
    return ['vpc-12345', 'vpc-7896']


# FIXME: why use a temp file?
def convert_to_base64(script):
    p, buildpack_path = tempfile.mkstemp()
    buildfile = open(buildpack_path, 'w')
    request.files[script].save(buildfile)
    buildfile.close
    with open(buildpack_path, "rb") as buildfile:
        result = base64.b64encode(buildfile.read())
    buildfile.close
    os.remove(buildpack_path)
    return result


# Web UI App
def create_app():
    app = Flask(__name__)

    Bootstrap(app)

    @app.route('/web/')
    def web_index():
        return render_template('index.html')

    @app.route('/web/app-list')
    def web_app_list():
        return render_template('app_list.html', apps=get_ghost_apps())

    @app.route('/web/app-create')
    def web_app_create():
        return render_template('app_create.html', types=aws_data.instance_type, roles=instance_role.role, envs=env.env, vpcs=get_vpc())

    @app.route('/web/module-deploy', methods=['POST'])
    def web_app_select_modules():
        try:
            modules = requests.get(url_apps+'/'+request.form['_id'], headers=headers, auth=auth).json()['modules']
        except:
            modules = ['Failed to retrieve Modules']

        code_modules = (module for module in modules if module['scope'] == 'code')

        return render_template('select_module.html', id=request.form['_id'], modules=code_modules)

    @app.route('/web/create-job', methods=['POST'])
    def web_job_create():
        job = {}
        job['user'] = 'web'
        job['command'] = 'deploy'
        job['app_id'] = request.form['app-id']

        module = {}
        module['name'] = request.form['module-name']
        modules = []
        modules.append(module)

        job['modules'] = modules

        try:
            eve_response = requests.post(url=url_jobs, data=json.dumps(job), headers=headers, auth=auth).content
        except:
            eve_response = 'Failed to create job'

        return render_template('action_completed.html', message=eve_response)

    @app.route('/web/result', methods=['POST'])
    def web_app_deploy():
        app = {}
        module = {}
        build_infos = {}
        autoscale = {}
        if 'module-build_pack' in dict(request.files).keys():
            module['build_pack'] = convert_to_base64('module-build_pack')
        if 'module-post_deploy' in dict(request.files).keys():
            module['post_deploy'] = convert_to_base64('module-post_deploy')
        for key in request.form.keys():
            if key.find('module') >= 0:
                module[key[7:]] = request.form[key]
            elif key.find('build_infos') >= 0:
                build_infos[key[12:]] = request.form[key]
            elif key.find('autoscale') >= 0:
                autoscale[key[11:]] = request.form[key]
            else:
                app[key] = request.form[key]
        # app['autoscale'] = autoscale
        # app['build_infos'] = build_infos
        app['modules'] = [module]

        try:
            eve_response = requests.post(url=url_jobs, data=json.dumps(app), headers=headers, auth=auth).content
            print(eve_response)
        except:
            eve_response = 'Failed to create job'

        return render_template('action_completed.html', message=eve_response)

    return app


def run_web_ui():
    app = create_app()
    app.run(host='0.0.0.0', port=5001, debug=True)
