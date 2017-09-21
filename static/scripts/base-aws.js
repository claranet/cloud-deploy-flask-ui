var provider = 'aws';

if ($('#assumed_account_id').val() && $('#assumed_role_name').val()) {
    var provider_identity_query = '?assumed_account_id=' + $('#assumed_account_id').val() + '&assumed_role_name=' + $('#assumed_role_name').val() + '&assumed_region_name=' + $('#assumed_region_name').val();
} else {
    var provider_identity_query = '';
}

function clear_provider_identity() {
    provider_identity_query = '';
}

function ghost_update_ec2_regions_confirm() {
    if (confirm('Refreshing region may also refresh all other resources that depends on it.')) {
        ghost_update_ec2_regions();
        $('select#region').change();
    }
}

function ghost_update_ec2_regions() {
    $('#region').find('option').remove();
    $.ajax("/web/" + provider + "/regions" + provider_identity_query).done(function(data) {
        // Update instance types select input options
        $.each(data,function(key, value) {
        $('#region').append('<option value=' + key + '>' + value + '</option>');
        });
        $('#region').selectpicker('refresh');
    }).fail(function() {
        alert("Failed to retrieve Regions");
    });
}

function ghost_update_ec2_instancetypes(region) {
    $('#instance_type').find('option').remove();
    $.ajax("/web/" + provider + "/regions/" + region + "/ec2/instancetypes" + provider_identity_query).done(function(data) {
        // Update instance types select input options
        $.each(data,function(key, value) {
        $('#instance_type').append('<option value=' + key + '>' + value + '</option>');
        });
        $('#instance_type').selectpicker('refresh');
    }).fail(function() {
        alert("Failed to retrieve EC2 instance types for region " + region);
    });
}

function ghost_update_ec2_vpcs(region) {
    $('#vpc_id').find('option').remove();
    $.ajax("/web/" + provider + "/regions/" + region + "/vpc/ids" + provider_identity_query).done(function(data) {
        // Update VPCs select input options
        $.each(data,function(key, value) {
        $('#vpc_id').append('<option value=' + key + '>' + value + '</option>');
        });
        $('select#vpc_id').change();
        $('#vpc_id').selectpicker('refresh');
    }).fail(function() {
        alert("Failed to retrieve EC2 VPCs for region " + region);
    });
}

function ghost_update_ec2_keys(region) {
    $('select#environment_infos-key_name').find('option').remove();
    $.ajax("/web/" + provider + "/regions/" + region + "/ec2/keypairs" + provider_identity_query).done(function(data) {
        // Update Key Pairs select input options
        $.each(data,function(key, value) {
        $('select#environment_infos-key_name').append('<option value=' + key + '>' + value + '</option>');
        });
        $('select#environment_infos-key_name').selectpicker('refresh');
    }).fail(function() {
        alert("Failed to retrieve EC2 KeyPairs for region " + region);
    });
}

function ghost_update_iam_profiles(region) {
    $('select#environment_infos-instance_profile').find('option').remove();
    $.ajax("/web/" + provider + "/regions/" + region + "/iam/profiles" + provider_identity_query).done(function(data) {
        // Update Instance Profiles select input options
        $.each(data,function(key, value) {
        $('select#environment_infos-instance_profile').append('<option value=' + key + '>' + value + '</option>');
        });
        $('select#environment_infos-instance_profile').selectpicker('refresh');
    }).fail(function() {
        alert("Failed to retrieve IAM Instance Profiles for region " + region);
    });
}

function ghost_update_vpc_sgs(region, vpc_id) {
    $('[id^=environment_infos-security_groups]').find('option').remove();
    $.ajax("/web/" + provider + "/regions/" + region + "/vpc/" + vpc_id + "/sg/ids" + provider_identity_query).done(function(data) {
        // Update SGs select input options
        $.each(data, function(key, value) {
            $.each($('[id^=environment_infos-security_groups]'), function(index) {
            $(this).append('<option value=' + key + '>' + value + '</option>');
            });
        });
        $('[id^=environment_infos-security_groups]').selectpicker('refresh');
    }).fail(function() {
        alert("Failed to retrieve Segurity Groups for region " + region);
    });
}

function ghost_update_vpc_subnets(region, vpc_id, for_build) {
    if (!for_build) {
    $('[id^=environment_infos-subnet]').find('option').remove();
    } else {
    $('#build_infos-subnet_id').find('option').remove();
    }
    $.ajax("/web/" + provider + "/regions/" + region + "/vpc/" + vpc_id + "/subnet/ids" + provider_identity_query).done(function(data) {
        // Update Subnets select input options
        $.each(data, function(key, value) {
        if (for_build) {
            $('#build_infos-subnet_id').append('<option value=' + key + '>' + value + '</option>');
        } else {
            $.each($('[id^=environment_infos-subnet]'), function(index) {
            $(this).append('<option value=' + key + '>' + value + '</option>');
            });
        }
        });
        if (!for_build) {
        $('[id^=environment_infos-subnet]').selectpicker('refresh');
        } else {
        $('#build_infos-subnet_id').selectpicker('refresh');
        }
    }).fail(function() {
        alert("Failed to retrieve Subnet for region " + region + " and VPC id "  + vpc_id);
    });
}

function ghost_update_ec2_amis(region) {
    $('[id^=build_infos-source_ami]').find('option').remove();
    $.ajax("/web/" + provider + "/regions/" + region + "/ami/ids" + provider_identity_query).done(function(data) {
        // Update AMIs select input options
        $.each(data, function(key, value) {
            $.each($('[id^=build_infos-source_ami]'), function(index) {
            $(this).append('<option value=' + key + '>' + value + '</option>');
            });
        });
        $('[id^=build_infos-source_ami]').selectpicker('refresh');
    }).fail(function() {
        alert("Failed to retrieve AMIs");
    });
}

function ghost_update_container_images() {
    $('[id^=build_infos-container]').find('option').remove();
    $.ajax("/web/container/image/ids").done(function(data) {
        $.each(data, function(key, value) {
            $.each($('[id^=build_infos-container]'), function(index) {
            $(this).append('<option value=' + key + '>' + value + '</option>');
            });
        });
        $('[id^=build_infos-container]').selectpicker('refresh');
    }).fail(function() {
        alert("Failed to retrieve container images");
    });
}

function ghost_update_ec2_asgs(region) {
    $('#autoscale-as_name').find('option').remove();
    $.ajax("/web/" + provider + "/regions/" + region + "/ec2/autoscale/ids" + provider_identity_query).done(function(data) {
        // Update ASGs select input options
        $.each(data,function(key, value) {
        $('#autoscale-as_name').append('<option value=' + key + '>' + value + '</option>');
        });
        $('#autoscale-as_name').selectpicker('refresh');
    }).fail(function() {
        alert("Failed to retrieve EC2 AutoScaling Groups for region " + region);
    });
}

function ghost_update_feature_presets() {
    $('select#features-presets').find('option').remove();
    $.ajax('/web/feature/presets').done(function(data) {
        $.each(data,function(key, value) {
        $('select#features-presets').append('<option value=' + key + '>' + value + '</option>');
        });
        $('select#features-presets').selectpicker('refresh');
    }).fail(function() {
        alert("Failed to retrieve Feature Presets List");
    });
}

$('select#provider').change(function () {
    ghost_update_ec2_regions();
    provider = $(this).val();
});
$('select#region').change(function() {
    var region = $(this).val();
    ghost_update_ec2_instancetypes(region);
    ghost_update_ec2_vpcs(region);
    ghost_update_ec2_asgs(region);
    ghost_update_ec2_keys(region);
    ghost_update_ec2_amis(region);
    ghost_update_iam_profiles(region);
});
$('select#vpc_id').change(function() {
    var vpcid = $(this).val();
    ghost_update_vpc_sgs($('select#region').val(), vpcid);
    ghost_update_vpc_subnets($('select#region').val(), vpcid, true);
    ghost_update_vpc_subnets($('select#region').val(), vpcid, false);
});
$('#check_provider_creds').click(function(evt) {
    evt.preventDefault();
    account = $('#assumed_account_id').val();
    role =  $('#assumed_role_name').val();
    region =  $('#assumed_region_name').val();
    app_region = $('select#region').val();
    $.ajax("/web/" + provider + "/identity/check/" + account + "/" + role + "/" + region).done(function(data) {
        if (data.result) {
            $('#app_options_wrapper').slideDown('slow');
            provider_identity_query = '?assumed_account_id=' + $('#assumed_account_id').val() + '&assumed_role_name=' + $('#assumed_role_name').val() + '&assumed_region_name=' + $('#assumed_region_name').val();
            $('#check_provider_creds').html('<i class="glyphicon glyphicon-check"> </i> Credentials OK');
            if (app_region) {
                if (confirm('Do you want to refresh all resource fields?\nIt will use your new custom identity configuration.')) {
                    $('select#region').change(); // Will reload all select in the page
                }
            }
        } else {
            alert('Invalid Identity parameters, please correct them. ' + data.msg);
        }
    }).fail(function() {
        alert('Invalid Identity parameters, please correct them. ');
    });
});

function ghost_add_feature_entry_to_list(group_id_prefix, entry_id_prefix, entry_label, scroll_to) {
    var count = $("div.feature-details-modal").size();
    var clone = $("div.feature-details-modal:last").clone();
    clone.attr("id", "feature-details-" + count);

    clone = ghost_update_entry(clone, count);
    clone.find('.feature_provisioner').attr('data-index', count);
    clone.find('.ansible-role-parameters-form').attr('id', 'ansible-role-parameters-form-'+count);

    // DOM Insert
    clone.appendTo(".panel-features");

    ghost_add_entry_to_list(group_id_prefix, entry_id_prefix, entry_label, scroll_to);
    $('tr[data-' + entry_id_prefix + ']:last').find('a.edit-entry').attr('data-target', '#feature-details-' + count);

    ghost_update_feature_form_details($('#feature-details-' + count).find('select[name$="feature_provisioner"]'));
    $('#feature-details-' + count).modal('show');
}

function ghost_add_entry_to_list(group_id_prefix, entry_id_prefix, entry_label, scroll_to) {
    var count = $("tr[data-" + entry_id_prefix + "]").size();
    var clone = $("tr[data-" + entry_id_prefix + "]:first").clone();

    clone.attr("id", entry_id_prefix + "_" + count);

    clone = ghost_update_entry(clone, count);

    // DOM Insert
    clone.appendTo("table#" + group_id_prefix + "_list");
    
    // CodeMirror update
    initCodeMirror();

    if (scroll_to) {
        // ScrollTo the new element
        $('#' + entry_id_prefix + "_" + count)[0].scrollIntoView();
    }
}

function ghost_update_entry(clone, count) {
    clone.find("input, select, textarea, .readonly").each(function() {
        var old_id = $(this).attr('id');
        $(this).val(null);
        if (old_id) {
            var new_id = old_id.replace(/-[0-9]+/i, '-' + count);
            $(this).attr("id", new_id);
            $(this).attr("name", new_id);

            var field_label = clone.find("label[for='" + old_id + "']");
            field_label.attr("for", new_id);
        }
    });
    clone.find(".readonly").each(function() {
        $(this).html('');
    });

    var slt = clone.find('select:not([readonly], [data-classic-select])').each(function() {
        $(this).parent().before($(this));
    });

    // Bootstrap Dynamic Select - update
    clone.find('.bootstrap-select').remove();
    clone.find('select:not([readonly], [data-classic-select])').selectpicker({
        style: 'btn-default',
        liveSearch: true,
        dropupAuto:  false
    });

    // CodeMirror cleaning
    clone.find('.CodeMirror').remove();
    clone.find('textarea').each(function(index, elem) {
        $(elem).css('display', 'block');
        $(elem).unbind();
    });

    return clone;
}

function ghost_del_feature_entry_from_list(entry_del_link, entry_id_prefix) {
    ghost_del_entry_from_list(entry_del_link, entry_id_prefix);
    var count = $("div.feature-details-modal").size();
    var entry = $($(entry_del_link).attr('data-target'));
    ghost_cleanup_entry(count, entry);
}

function ghost_del_entry_from_list(entry_del_link, entry_id_prefix) {
    var count = $("tr[data-" + entry_id_prefix + "]").size();
    var entry = $(entry_del_link).parent().parent();
    ghost_cleanup_entry(count, entry);
}

function ghost_cleanup_entry(count, entry) {
    if (count > 1) {
        entry.remove();
    } else {
        // Do not remove element, just clear inputs
        entry.find("input, textarea").val(null);
        entry.find("select").each(function(index, elem) {
            $(this).val($(this).children("option:first").val());
            $(this).selectpicker('refresh');
        });
        entry.find("input[type=checkbox]").prop("checked", "");
    }
}

function dropHandler(dropEvent) {
    dropEvent.stopPropagation();
    dropEvent.preventDefault();
    var reader = new FileReader();
    reader.onloadend = function(loadEvent) {
        if (loadEvent.target.readyState == FileReader.DONE) {
            dropEvent.target.value = loadEvent.target.result;
        }
    };
    reader.readAsText(dropEvent.dataTransfer.files[0],"UTF-8");
}
