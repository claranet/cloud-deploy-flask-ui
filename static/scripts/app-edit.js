function ghost_update_feature_form_details(provisioner_select) {
    provisioner_type = $(provisioner_select).val();
    container = $(provisioner_select).parent().parent().parent().parent().parent();
    $(container).find('.provisioner_type:not(.' + provisioner_type + ')').hide();
    $(container).find('.provisioner_type.' + provisioner_type).show();
    if (provisioner_type == 'ansible') {
        ghost_update_feature_ansible_role_parameters(container);
    }
}

function ghost_update_feature_view(provisioner_select) {
    provisioner_type = $(provisioner_select).val();
    feature_index = $(provisioner_select).parent().parent().parent().parent().attr('data-index');
    container = $('#feature_' + feature_index);
    img = $(container).find('img.feature-provisioner');
    img.attr('src', img.attr('data-base-uri').replace('[]', provisioner_type));
    img.attr('title', 'Provisioner ' + provisioner_type);
    img.attr('alt', provisioner_type);
    if (provisioner_type == 'salt') {
        $(container).find('#features-'+feature_index+'-view-feature_name').html($('#features-'+feature_index+'-feature_name').val());
        $(container).find('#features-'+feature_index+'-view-feature_val').html($('#features-'+feature_index+'-feature_version').val());
    } else {
        $(container).find('#features-'+feature_index+'-view-feature_name').html($('#features-'+feature_index+'-feature_selected_name').val());
        $(container).find('#features-'+feature_index+'-view-feature_val').html($('#features-'+feature_index+'-feature_parameters').val());
    }
}

function ghost_update_feature_ansible_role_parameters(container) {
    role_select = $(container).find('select[name$="feature_selected_name"]')
    role = $(role_select).val();
    $(container).find('.ansible-role-parameters-form').html('');
    $.ajax('/web/feature/ansible/role-schema/'+role).done(function(data) {
        $(container).find('.ansible-role-parameters-form').jsonForm({
            schema: data,
            onSubmit: function (errors, values) {
                if (errors) {
                    alert(errors);
                } else {
                    console.log('ok');
                }
            }
        });
    }).fail(function() {
        alert("Failed to retrieve Ansible role schema");
    });
}

(function() {
    $('.quick-submit').click(function (evt) {
        evt.preventDefault();
        $('#app-form #submit').click();
    });
    var oneDropDone = false;
    var list = document.getElementById("menu-modules-list");
    $('#menu-modules-list li').addClass('draggable');
    Sortable.create(list, {
        animation: 150,
        onEnd: function (/**Event*/evt) {
            if (evt.oldIndex != evt.newIndex) {
                if (!oneDropDone) {
                    oneDropDone = true;
                    $('#app-form').submit(function () {
                        /* Rewrite indexes for Flask */
                        $('#modules_list tr').each(function(index, mod) {
                            $(this).find('[name]').each(function() {
                                newModAttr = $(this).attr('name').replace(/modules-[0-9]*-/i, 'modules-'+index+'-');
                                $(this).attr('name', newModAttr);
                                $(this).attr('id', newModAttr);
                            });
                        });
                    });
                }

                /* DOM Swap */
                modules = $('#modules_list tr');
                oldModule = $(modules.get(evt.oldIndex));
                if (evt.oldIndex > evt.newIndex)
                    $(modules.get(evt.newIndex)).before(oldModule.clone(true));
                else
                    $(modules.get(evt.newIndex)).after(oldModule.clone(true));
                oldModule.remove();
            }
        },
    });
    $('#modules_list').on('focusout', 'input[name$="module_name"]', function () {
        var module_name = $(this).val();
        var menu_link = $('ul.navbar-fixed-left li a[href="#'+$(this).parentsUntil('tr').parent().attr('id').replace('_', '-')+'"] span');
        menu_link.text(module_name);
    });
    var listFeatures = $("#features_list tbody").get(0);
    $('#features_list tr').addClass('draggable');
    Sortable.create(listFeatures, {
        animation: 150,
        onEnd: function (/**Event*/evt) {
            if (!oneDropDone) {
                oneDropDone = true;
                $('#app-form').submit(function () {
                    /* Rewrite indexes for Flask */
                    $('#features_list tr').each(function(index, mod) {
                        $(this).find('[name]').each(function() {
                            newModAttr = $(this).attr('name').replace(/features-[0-9]*-/i, 'features-'+index+'-');
                            $(this).attr('name', newModAttr);
                            $(this).attr('id', newModAttr);
                        });
                    });
                });
            }
        },
    });
    $('.panel-features').on('change', 'select[name$="feature_provisioner"]', function () {
        ghost_update_feature_form_details($(this));
    });
    $('.feature-details-modal').on('show.bs.modal', function (event) {
        ghost_update_feature_form_details($(this).find('.modal-body select[name$="feature_provisioner"]'));
    });
    $('.feature-details-modal').on('hide.bs.modal', function (event) {
        ghost_update_feature_view($(this).find('.modal-body select[name$="feature_provisioner"]'));
    });
    ghost_update_feature_presets();
    var ghost_client_name = window.location.hostname.replace('.ghost.morea.fr', '');
    $('.feature-import').click(function(evt) {
        evt.preventDefault();
        preset_file = $('select#features-presets').val();
        new_index = 0;
        var ghost_app_name = $('#name').val();
        var ghost_app_env = $('#env').val();
        var ghost_app_role = $('#role').val();
        $.ajax('/web/feature/presets/import/' + preset_file).done(function(data) {
            desc = data['description'];
            feats = data['features'];
            $.each(feats, function(index, feat_object) {
                feature_name = '' + feat_object['name'];
                feature_val = '' + feat_object['value'];
                feature_val = feature_val
                    .replace('${GHOST_CLIENT}', ghost_client_name)
                    .replace('${GHOST_ENV}',    ghost_app_env)
                    .replace('${GHOST_ROLE}',   ghost_app_role)
                    .replace('${GHOST_APP}',    ghost_app_name);
                feature_provisioner = '' + feat_object['provisioner'];
                new_index = $("tr[data-feature]").size();
                ghost_add_entry_to_list('features', 'feature', 'Feature', false);
                $('#features-'+new_index+'-feature_name').val(feature_name);
                $('#features-'+new_index+'-feature_version').val(feature_val);
                $('#features-'+new_index+'-feature_provisioner').val(feature_provisioner);
            });
        }).fail(function() {
            alert("Failed to retrieve Feature Preset " + preset_file);
        });
    });
    $('.refresh-select').each(function(index) {
        $(this).prev().addClass('select-panel');
    });
    $('.refresh-select').click(function (evt) {
        evt.preventDefault();
        jsCall = $(this).attr('data-call');
        eval(jsCall);
        selectElt = $(this).attr('data-target');
        $(selectElt).selectpicker('refresh')
    });
    $('#role,#env').parent().addClass('select-generic-options');
    $('#env').parent().attr('data-select-id', 'env');
    $('#role').parent().attr('data-select-id', 'role');
    $('#app-form').on('click', '.btn-select-append-option', function(evt) {
        evt.preventDefault();
        select_id = $(this).parents('.select-generic-options').attr('data-select-id');
        new_val = $('#' + select_id).parent().find('.bs-searchbox input').val();
        $('#' + select_id).append('<option value="'+new_val+'" selected="">'+new_val+'</option>');
        $('#' + select_id).selectpicker("refresh");
    });
    $('#instance_type').change(function() {
        big_test = /.[0-9]+xlarge/;
        if (big_test.test($(this).val())) {
            $(this).parent().addClass('warning-big-instance-type');
        } else {
            $(this).parent().removeClass('warning-big-instance-type');
        }
    });

    $('#safedeployment-lb_type').change(function() {
        if ($(this).val() == 'haproxy') {
            $('.haproxy-params').show();
        } else {
            $('.haproxy-params').hide();
        }
    });
    $('#use_custom_identity').change(function(evt) {
        if (this.checked) {
            $('#identity_provider').slideDown('slow');
            $('#app_options_wrapper').slideUp('slow');
        } else {
            // Reset custom identity params
            clear_provider_identity();
            app_region = $('select#region').val();
            if (app_region) {
                if (confirm('Do you want to refresh all resource fields?\nIt will use the default identity configuration.')) {
                    $('select#region').change(); // Will reload all select in the page
                }
            }
            // UI update
            $('#identity_provider').slideUp('slow');
            $('#app_options_wrapper').slideDown('slow');
        }
    });
    $('#blue_green-enable_blue_green').change(function(e) {
        $('#swap_scripts').slideToggle('slow');
    });
    $('.app-actions a, #navbar li a').click(function(evt) {
        return confirm('Do you want to leave this page without saving your modifications?');
    });

    initCodeMirror();
})();

Array.prototype.contains = function(element){
    return this.indexOf(element) > -1;
};
$('#modules_list').on('focusout', 'td input[name$="path"]', function () {
    var path = $(this).val();
    if (forbidden_paths.contains(path)) {
        $(this).popover({
            content: '<span><i class="glyphicon glyphicon-warning-sign">&nbsp;</i>Module path must not be in '+forbidden_paths.join()+'</span>',
            html: true,
            placement: 'top'
        });
        $(this).popover('show');
    } else {
        $(this).popover('hide');
        $(this).popover('destroy');
    }
});
