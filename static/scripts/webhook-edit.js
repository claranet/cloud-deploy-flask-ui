function get_app_modules_names(app_id) {
    $('#module').find('option').remove();
    disable_submit_button();
    $.ajax("/web/aws/appinfos/" + app_id +"/modules/names").done(function(data) {
        $.each(data, function(key, value) {
            $('#module').append('<option value=' + value + '>' + value + '</option>');
        });
        $("#module option:nth-child(1)").attr("selected", "selected");
        $('#module').selectpicker('refresh');
        enable_submit_button();
    }).fail(function() {
        alert("Failed to retrieve Modules for App " + app_id);
        enable_submit_button();
    });
}

(function() {
    $('#command').change(function() {
        show_options_fields();
    })

    refresh_safe_deploy_options(false);

    $('#app_id').change(function () {
        var app_id = $(this).val();
        get_app_modules_names(app_id)
    });

    $('.app-actions a, #navbar li a').click(function(evt) {
        return confirm('Do you want to leave this page without saving your modifications?');
    });
})();

