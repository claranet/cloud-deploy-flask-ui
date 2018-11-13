// based on https://stackoverflow.com/questions/31593297/using-execcommand-javascript-to-copy-hidden-text-to-clipboard
function setClipboard(value) {
    var tempInput = document.createElement("input");
    tempInput.style = "position: absolute; left: -1000px; top: -1000px";
    tempInput.value = value;
    document.body.appendChild(tempInput);
    tempInput.select();
    document.execCommand("copy");
    document.body.removeChild(tempInput);
}

$(function () {
    $(document).on('click', '[data-toggle="popover"]', function() {
        var $this = $(this);
        //if not already initialized
        if (!$this.data('bs.popover')) {
            $this.popover({
                html: true
            }).popover('show');
        }
    });
    $(document).on('click', '[data-type="clipboard-copy"]', function() {
        var data_target = $(this).attr('href');
        setClipboard($(data_target).val());
        return false;
    });
})
