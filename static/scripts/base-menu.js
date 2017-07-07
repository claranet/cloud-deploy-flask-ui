function updateMenusPositions() {
    var headerHeight = $("#header").outerHeight(true) + $('.ghost-titlebar').outerHeight(true) + 6;
    var visibleHeight = $(window).height()- headerHeight - $('footer').height();
    $('.container[role=main]').css('height', visibleHeight + 'px');
    $('#left-menu').css('height', visibleHeight + 'px');
    $("#left-menu").css('top', headerHeight + "px");
}
$(window).on('resize', function() {
    updateMenusPositions();
});
$(document).ready(function() {
    updateMenusPositions();
});
