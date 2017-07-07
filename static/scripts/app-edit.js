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
                        /* -- TODO Update Manifest trigger
                        if (confirm('Module order has changed. Do you want to update the App MANIFEST ? If No, the MANIFEST will be updated on the next deploy command.')) {
                            $('#app-form').append('<input type="hidden" id="update_manifest" name="update_manifest" value="1">');
                        }*/
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
    $('#modules_list').on('focusout', 'td input[name$="path"]', function () {
        var path = $(this).val();
        if (path == '/' || path == '/tmp' || path == '/var' || path == '/etc') {
            $(this).popover({
                content: '<span><i class="glyphicon glyphicon-warning-sign">&nbsp;</i>Module path should not be "/", "/tmp", "/etc" or "/var"</span>',
                html: true,
                placement: 'top'
            });
            $(this).popover('show');
        } else {
            $(this).popover('hide');
            $(this).popover('destroy');
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
})();

(function() {
    initCodeMirror();
})();