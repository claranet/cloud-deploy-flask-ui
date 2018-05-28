$(document).ready(function() {
    $(document).on('click', 'button.app-infos-btn', function(evt) {
        $('#as-instance-details fieldset').addClass('hide');
    });
    $(document).on('click', '.instance-item', function(evt) {
        evt.preventDefault();
        instance_content = $(this).next().html();
        $('.instance-item').removeClass('focus');
        $(this).addClass('focus');
        $('#as-instance-details fieldset').removeClass('hide');
        $('#as-instance-details fieldset').html(instance_content);
        $('#as-instance-details [data-toggle="tooltip"]').tooltip();
    });
    $(document).on('click', '#as-elb a', function(evt) {
        evt.preventDefault();
        $('#as-elb a').removeClass('btn-colored');
        $(this).addClass('btn-colored');

        $('.instance-item').removeClass(function (index, css) {
            return (css.match (/(^|\s)hl-\S+/g) || []).join(' ');
        });
        instances = $(this).attr('data-instances');
        color = $(this).attr('data-color');
        $(instances).addClass('hl-'+color);
    });
});
