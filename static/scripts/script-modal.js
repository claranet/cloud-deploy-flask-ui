$(document).ready(function() {
    $('.ghost_abbrev_field').on('shown.bs.modal', function (event) {
        // If necessary, you could initiate an AJAX request here (and then do the updating in a callback).
        // Update the modal's content. We'll use jQuery here, but you could use a data binding library or other methods instead.
        var modal = $(this);
        var code = modal.find('.CodeMirror');
        if (code.length < 1) {
            var area = modal.find('textarea').get(0);
            var editor = CodeMirror.fromTextArea(area, {
                lineNumbers: true,
                lineWrapping: true,
                styleActiveLine: true,
                mode: 'shell',
                readOnly: true,
            });
        }
    });
});
