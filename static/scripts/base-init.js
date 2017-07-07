$(document).ready(function() {
    $('form').submit(function(evt) {
        btn = $(this).find('input#submit');
        if (btn.hasClass('disabled')) {
            evt.preventDefault();
        }
        btn.addClass('disabled');
    });
});

function initCodeMirror() {
    $('textarea').each(function(index, elem) {
        $(elem).focus(function() {
            $(elem).unbind("focus");
            var editor = CodeMirror.fromTextArea(this, {
                lineNumbers: true,
                viewportMargin: Infinity,
                lineWrapping: true,
                mode: 'shell',
            });
            $(this).parent().parent().addClass('script-panel');
            // setTimeout(function(){ editor.refresh(); }, 3000); // try to hack the editor cursor bug
        });
    });
}

/*
health status modal
    */
$(document).ready(function() {
    $('#ghost-health-status-modal').on('hidden.bs.modal', function() {
        $(this).removeData();
    });
});

$('input#submit').prepend('<span class="glyphicon glyphicon-ok"></span>');
$('input#submit').addClass('btn-raised btn-info');

$.material.init();
$(function () {
    $('[data-toggle="tooltip"]').tooltip()
})

$(document).ready(function() {
    $('select:not([readonly], [data-classic-select])').selectpicker({
        style: 'btn-default',
        noneResultsText: 'No results matched {0} <button title="Create a new entry for this unknown option" class="btn-select-append-option btn btn-raised btn-success btn-xs"><i class="glyphicon glyphicon-plus"></i></button>',
        liveSearch: true,
        dropupAuto:  false
    });
});

var $loading = $('#ajaxSpinnerImage').hide();
$(document).ajaxStart(function () {
    $loading.show();
}).ajaxStop(function () {
    $loading.hide();
});
