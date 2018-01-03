// Depending on provisioner type, this function shows/enables the right DOM elements
function ghost_update_feature_form_details(provisioner_select) {
    provisioner_type = $(provisioner_select).val();
    container = $(provisioner_select).parents('.modal-body');
    ghost_update_feature_list_name(provisioner_type, container);
    container.find('div[data-provisioner-type]:not([data-provisioner-type="' + provisioner_type + '"])').hide();
    container.find('div[data-provisioner-type="' + provisioner_type + '"]').show();
}

// Reload feature list depending on Salt or Ansible
function ghost_update_feature_list_name(provisioner_type, container) {
    feature_name_list = container.find('[id$=feature_name]');
    cur_val = feature_name_list.val();
    feature_name_list.find('option').remove();
    $.ajax('/web/feature/' + provisioner_type + '/inventory').done(function(data) {
        // Update instance types select input options
        $.each(data,function(key, value) {
            feature_name_list.append('<option value=' + key + '>' + value + '</option>');
        });
        feature_name_list.val(cur_val);
        feature_name_list.selectpicker('refresh');
        feature_name_list.change();
    }).fail(function() {
        alert("Failed to retrieve features");
    });
}

// When the Feature details Modal is closed, we need to update the associated table>tr feature element
function ghost_update_feature_view(provisioner_select) {
    provisioner_type = $(provisioner_select).val();
    feature_index = $(provisioner_select).parents('.feature_provisioner').attr('data-index');
    container = $('#feature_' + feature_index);
    img = $(container).find('img.feature-provisioner');
    img.attr('src', img.attr('data-base-uri').replace('[]', provisioner_type));
    img.attr('title', provisioner_type);
    img.attr('alt', provisioner_type);
    $(container).find('#features-'+feature_index+'-view-feature_name').html($('#features-'+feature_index+'-feature_name').val());
    if (provisioner_type == 'salt') {
        $(container).find('#features-'+feature_index+'-view-feature_val').html($('#features-'+feature_index+'-feature_version').val());
        $('#features-'+feature_index+'-feature_parameters').val('null');
    } else {
        $('#features-'+feature_index+'-feature_version').val('');
        ansible_role_parameter_form = $('#ansible-role-parameters-form-'+feature_index);
        $(ansible_role_parameter_form).submit();
        parameters_obj = JSON.parse($('#features-'+feature_index+'-feature_parameters').val() || "null");
        if (parameters_obj != null) {
            $(container).find('#features-'+feature_index+'-view-feature_val').html('');
            for (var key in parameters_obj) {
                $(container).find('#features-'+feature_index+'-view-feature_val').append(key+': '+ parameters_obj[key]+ '\n');
            }
        }
    }
    $('#ajaxSpinnerImage').hide();
}

// When selecting an Ansible Role from the Select, get the associated Schema and generates the appropriate form.
function ghost_update_feature_ansible_role_parameters(container) {
    wrap_provisioner = $(container).find('.feature_provisioner');
    if (wrap_provisioner.find('select[name$=feature_provisioner]').val() != 'ansible') {
        return;
    }
    role_select = $(container).find('select[name$="feature_name"]');
    feature_index = wrap_provisioner.attr('data-index');
    role = $(role_select).val();
    if (role == null) {
        role = $(role_select).find('option:first').val();
    }
    str_params = $(container).find('input[name$="feature_parameters"]').val();
    $.ajax('/web/feature/ansible/role-schema/'+role).done(function(data) {
        $(container).find('.ansible-role-parameters-form').html('').removeClass('jsonform');
        jQuery.removeData($(container).find('.ansible-role-parameters-form'));
        $(container).find('.ansible-role-parameters-form').jsonForm({
            schema: data,
            value: str_params == '' || str_params == '{}' ? undefined : JSON.parse(str_params),
            onSubmit: function (errors, values) {
                if (errors) {
                    console.log(errors);
                }
                else {
                    $('#features-'+feature_index+'-feature_parameters').val(JSON.stringify(values));
                }
            },
        });
        $.material.checkbox();
    }).fail(function() {
        alert("Failed to retrieve Ansible role schema");
    });
}

// Backport escapeSelector function from JSONForm
var JSONForm_escapeSelector = function (selector) {
    return selector.replace(/([ \!\"\#\$\%\&\'\(\)\*\+\,\.\/\:\;<\=\>\?\@\[\\\]\^\`\{\|\}\~])/g, '\\$1');
};
// Extends JSONForm.elementTypes['array']['onInsert'] function with our custom behavior
var jsonform_array_insert_fct = JSONForm.elementTypes['array']['onInsert'];
JSONForm.elementTypes['array']['onInsert'] = function (evt, node) {
    jsonform_array_insert_fct(evt, node);
    var $nodeid = $(node.el).find('#' + JSONForm_escapeSelector(node.id));
    $('> span > a._jsonform-array-addmore', $nodeid).click(function (evt) {
        $.material.checkbox();
    });
};

function rewrite_feature_indexes() {
    /* Rewrite indexes for Flask */
    $('#features_list tr').each(function(index, mod) {
        $(this).find('[name]').each(function() {
            newModAttr = $(this).attr('name').replace(/features-[0-9]*-/i, 'features-'+index+'-');
            $(this).attr('name', newModAttr);
            $(this).attr('id', newModAttr);
        });
        $(this).find('[for]').each(function() {
            newModAttr = $(this).attr('for').replace(/features-[0-9]*-/i, 'features-'+index+'-');
            $(this).attr('for', newModAttr);
        });
        $(this).find('span[id]').each(function() {
            newModAttr = $(this).attr('id').replace(/features-[0-9]*-/i, 'features-'+index+'-');
            $(this).attr('id', newModAttr);
        });
        $(this).find('.edit-entry,.delete-entry').attr('data-target', '#feature-details-'+index);
        $(this).attr('id', 'feature_'+index);
    });
    $('.feature-details-modal').each(function(index, mod) {
        $(this).find('[name]').each(function() {
            newModAttr = $(this).attr('name').replace(/features-[0-9]*-/i, 'features-'+index+'-');
            $(this).attr('name', newModAttr);
            $(this).attr('id', newModAttr);
        });
        $(this).find('.feature_provisioner').attr('data-index', index);
        $(this).find('.ansible-role-parameters-form').attr('id', 'ansible-role-parameters-form-'+index);
        $(this).attr('id', 'feature-details-'+index);
        $(this).attr('aria-labelledby', 'myModalLabelFeature'+index);
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
                    rewrite_feature_indexes();
                });
            }
            /* DOM Swap - need to also re-order Modals */
            features_modals = $('.feature-details-modal');
            oldModal = $(features_modals.get(evt.oldIndex));
            clone = oldModal.clone(false);
            // Bootstrap Dynamic Select - update
            clone.find('select:not([readonly], [data-classic-select])').each(function() {
                $(this).parent().before($(this));
            });
            clone.find('.bootstrap-select').remove();
            clone.find('select:not([readonly], [data-classic-select])').selectpicker({
                style: 'btn-default',
                liveSearch: true,
                dropupAuto:  false
            });
            clone.find('select:not([readonly], [data-classic-select])').each(function() {
                // Jquery hack: need to re-affect previous select values
                $(this).val(oldModal.find('#' + $(this).attr('id')).val());
            });
            if (evt.oldIndex > evt.newIndex)
                $(features_modals.get(evt.newIndex)).before(clone);
            else
                $(features_modals.get(evt.newIndex)).after(clone);
            oldModal.remove();
        },
    });
    $('.panel-features').on('change', 'select[name$="feature_provisioner"]', function () {
        ghost_update_feature_form_details($(this));
    });
    $('.panel-features').on('change', 'select[name$="feature_name"]', function () {
        ghost_update_feature_ansible_role_parameters($(this).parent().parent().parent().parent().parent());
    });
    $('.panel-features').on('show.bs.modal', '.feature-details-modal', function (event) {
        ghost_update_feature_form_details($(this).find('.modal-body select[name$="feature_provisioner"]'));
    });
    $('.panel-features').on('hide.bs.modal', '.feature-details-modal', function (evt) {
        if ($(this).find('.has-error').length > 0) {
            alert('Please correct invalid fields before saving this form.');
            evt.preventDefault();
            evt.stopImmediatePropagation();
            return false;
        } else {
            ghost_update_feature_view($(this).find('.modal-body select[name$="feature_provisioner"]'));
        }
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
                feature_parameters = '' + feat_object['parameters'];
                new_index = $("tr[data-feature]").size();
                ghost_add_feature_entry_to_list('features', 'feature', 'Feature', false, false);
                $('#features-'+new_index+'-feature_name option[selected]').attr('value', feature_name);
                $('#features-'+new_index+'-feature_name').val(feature_name).selectpicker('refresh');
                $('#features-'+new_index+'-feature_version').val(feature_val);
                $('#features-'+new_index+'-feature_provisioner').val(feature_provisioner).selectpicker('refresh');
                ghost_update_feature_view($('#features-'+new_index+'-feature_provisioner'));
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
