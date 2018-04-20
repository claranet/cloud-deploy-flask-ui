function show_options_fields()  {
    $('.wrap').hide();
    if ($('#command').val() == 'deploy') {
        $('.wrap.modules').show();
        $('.wrap.fabric_execution_strategy').show();
        $('.wrap.safe_deployment').show();
    } else if ($('#command').val() == 'redeploy') {
        $('.wrap.deploy_id').show();
        $('.wrap.fabric_execution_strategy').show();
        $('.wrap.safe_deployment').show();
    } else if ($('#command').val() == 'recreateinstances') {
        $('.wrap.rolling_update').show();
    } else if ($('#command').val() == 'buildimage') {
        $('.wrap.instance_type').show();
        $('.wrap.skip_provisioner_bootstrap').show();
    } else if ($('#command').val() == 'createinstance') {
        $('.wrap.subnet').show();
        $('.wrap.private_ip_address').show();
        if ($('#subnet option').first().val() == '') {
            /*only update if needed*/
            get_app_subnets(app_id);
        }
    } else if ($('#command').val() == 'executescript') {
        $('.wrap.to_execute_script').show();
        $('.wrap.script_module_context').show();
        $('.wrap.execution_strategy').show();
        initCodeMirror();
        refresh_execute_script_fields();
    /* BlueGreen commands */
    } else if ($('#command').val() == 'preparebluegreen') {
        $('.wrap.prepare_bg_copy_ami').show();
        $('.wrap.prepare_create_temp_elb').show();
    } else if ($('#command').val() == 'swapbluegreen') {
        $('.wrap.swapbluegreen_strategy').show();
    } else if ($('#command').val() == 'purgebluegreen') {
        // No option available
    }
}

function refresh_options_list() {
    $('#command option, #safe_deployment_strategy option, #rolling_update_strategy option, #single_host_instance option, #execution_strategy option').each(function() {
        cmd = $(this).val();
        desc = $(this).text();
        $(this).text(cmd);
        $(this).attr('data-subtext', ' - ' + desc);
    });
    $('#command, #safe_deployment_strategy, #rolling_update_strategy, #single_host_instance, #execution_strategy').selectpicker('refresh');
}

function enable_submit_button() {
    $('#submit').prop('disabled', false);
}

function disable_submit_button() {
    $('#submit').prop('disabled', true);
}

function get_app_subnets(app_id) {
    $('#subnet').find('option').remove();
    disable_submit_button();
    $.ajax("/web/aws/appinfos/" + app_id +"/subnet/ids").done(function(data) {
        // Update Subnets select input options
        $.each(data, function(key, value) {
            $('#subnet').append('<option value=' + key + '>' + value + '</option>');
        });
        $("#subnet option:nth-child(2)").attr("selected", "selected");
        $('#subnet').selectpicker('refresh');
        enable_submit_button();
    }).fail(function() {
        alert("Failed to retrieve Subnet for App " + app_id);
        enable_submit_button();
    });
}

function get_app_safe_deployment_possibilities(select_id, mode) {
    if (mode != 'append') {
        $(select_id).find('option').remove();
    }
    disable_submit_button();
    $.ajax("/web/apps/" + app_id + "/command/deploy/safe_possibilities").done(function(data) {
        $.each(data, function(key, value) {
        $(select_id).append('<option value=' + key + '>' + value + '</option>');
        });
        refresh_options_list();
        enable_submit_button();
    }).fail(function() {
        alert("Failed to retrieve Safe Strategies");
        enable_submit_button();
    });
}

function get_app_ec2_possibilities() {
    $('#single_host_instance').find('option').remove();
    disable_submit_button();
    $.ajax("/web/aws/regions/" + app_region + "/ec2/" + app_id + "/infos").done(function(data) {
        $.each(data, function(key, value) {
        $('#single_host_instance').append('<option value=' + key + '>' + value + '</option>');
        });
        refresh_options_list();
        enable_submit_button();
    }).fail(function() {
        alert("Failed to retrieve Safe Strategies");
        enable_submit_button();
    });
}

function refresh_safe_deploy_options(update_possibilities) {
    if ($('#safe_deployment').is(':checked')) {
        $('.wrap.safe_deployment_strategy').show();
        if (update_possibilities) {
            get_app_safe_deployment_possibilities('#safe_deployment_strategy');
        }
    } else {
        $('.wrap.safe_deployment_strategy').hide();
    }
    if ($('#rolling_update').is(':checked')) {
        $('.wrap.rolling_update_strategy').show();
        if (update_possibilities) {
            get_app_safe_deployment_possibilities('#rolling_update_strategy');
        }
    } else {
        $('.wrap.rolling_update_strategy').hide();
    }
}

function refresh_execute_script_fields() {
    if ($('#execution_strategy').val() == 'single') {
        $('.wrap.single_host_instance').show();
        $('.wrap.safe_deployment_strategy').hide();
        get_app_ec2_possibilities();
    } else {
        $('.wrap.single_host_instance').hide();
        $('.wrap.safe_deployment_strategy').show();
        get_app_safe_deployment_possibilities('#safe_deployment_strategy');
    }
}

(function() {
    show_options_fields();
    $('#command').change(function() {
        show_options_fields();
    });
    refresh_safe_deploy_options(false);
    $('#safe_deployment, #rolling_update').change(function() {
        refresh_safe_deploy_options(true);
    });

    refresh_options_list();

    $('#execution_strategy').change(function() {
        refresh_execute_script_fields();
    });

    $('#private_ip_address').focusout(function (){
        ip_input = $(this).val();
        subnet_input = $('#subnet').val();
        cidr = $('option[value='+subnet_input+']').text().split(' - ')[1].replace(')', '');
        if (ip_input && !cidr_match(ip_input, cidr)) {
            $(this).parent().parent().addClass('has-error');
            $('#submit').attr('disabled', 'disabled');
            alert("'" + ip_input + "' is not a valid IP for the choosen subnet with CIDR '" + cidr + "'")
        } else {
            $(this).parent().parent().removeClass('has-error');
            $('#submit').removeAttr('disabled');
        }
    });
})();

function ghost_update_command_deploy_revision(module_name, revision_id) {
    disable_submit_button();
    $.ajax("/web/apps/" + app_id + "/command/module/" + module_name).done(function(data) {
        // Update revision input default
        $('#' + revision_id).val(data);
        enable_submit_button();
    }).fail(function() {
        alert("Failed to retrieve last deployed revision for module " + module_name);
        enable_submit_button();
    });
}

function ghost_update_command_deploy_available_revisions(dom_module_prefix, module_name) {
    $('select[id=' + dom_module_prefix + '-available_revisions]').find('option').remove();
    disable_submit_button();
    $.ajax("/web/apps/" + app_id + "/module/" + module_name + "/available-revisions").done(function(data) {
        // Update available_revisionss select
        $.each(JSON.parse(data), function(index, elt) {
            key = elt[0];
            value = elt[1];
            $('select[id=' + dom_module_prefix + '-available_revisions]').append('<option value=' + key + '>' + value + '</option>');
        });
        $('select[id=' + dom_module_prefix + '-available_revisions]').selectpicker({
            style: 'btn-default',
            liveSearch: true,
            dropupAuto: true,
            size: 5
        });
        $('select[id=' + dom_module_prefix + '-available_revisions]').selectpicker('refresh');
        enable_submit_button();
    }).fail(function() {
        alert("Failed to retrieve all available revisions for module " + module_name);
        enable_submit_button();
    });
}

$('button.retrieve-available-revisions').click(function(evt) {
    evt.preventDefault();
    var module_prefix = $(this).attr('data-prefix').substr(0, $(this).attr('data-prefix').lastIndexOf("-"));
    var name_id = module_prefix + '-name';
    var module_name = $('input[type="hidden"][id=' + name_id + ']').attr('value');
    $('td#td-' + module_prefix + '-available_revisions').show();
    ghost_update_command_deploy_available_revisions(module_prefix, module_name);
});

function ghost_count_checked_modules() {
    var checked_modules_count = $('input[type="checkbox"][id^="modules"]:checked').length;
    $('#module_counter span').text(checked_modules_count);
}

$('input[type="checkbox"][id^="modules"]').change(function() {
    if ($(this).prop('checked')) {
        var module_prefix = $(this).attr('id').substr(0, $(this).attr('id').lastIndexOf("-"));
        var name_id = module_prefix + '-name';
        var revision_id = module_prefix + '-rev';
        var module_name = $('input[type="hidden"][id=' + name_id + ']').attr('value');
        ghost_update_command_deploy_revision(module_name, revision_id);
    }
    ghost_count_checked_modules();
});

$('#deploy_all_modules').change(function () {
    $('input[type="checkbox"][id^="modules"]').prop('checked', $(this).prop('checked')).trigger("change");
});

$('select[id^=modules-]').change(function() {
    var module_prefix = $(this).attr('id').substr(0, $(this).attr('id').lastIndexOf("-"));
    var revision_id = module_prefix + '-rev';
    var module_check = module_prefix + '-deploy';
    $('#' + revision_id).val($(this).val());
    $('#' + module_check).prop('checked', 'checked');
});