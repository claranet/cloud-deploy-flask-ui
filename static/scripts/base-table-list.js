var TableList = {
    currentPage: null,
    bottomReached: false,
    withQuery: null,
    xhrs: []
}

function fetchNextPage() {
    TableList.withQuery = $(location).attr('search') && $(location).attr('search') != "";
    if(!TableList.bottomReached) {
        $('tr#loadmoreajaxloader td').show();
        $('tr#backtotop td').hide();
        TableList.currentPage++;
        // Don't use 'href' attr, because it can contains the 'hash' attribute
        var currentURI = $(location).attr('origin') + $(location).attr('pathname') + $(location).attr('search');
        var loadMoreUrl = TableList.withQuery
            ? currentURI + '&page=' + TableList.currentPage
            : currentURI + '?page=' + TableList.currentPage;
        TableList.xhrs.push($.ajax({
            url: loadMoreUrl,
            success: function(html)
            {
                if (html.length > 2) {
                    $('tr#loadmoreajaxloader').before(html);
                    $('tr#loadmoreajaxloader td').hide();
                    if ($('.tablelist').height() <= $('.container[role=main]').innerHeight()) { //fetchfing next page to fill the document
                        fetchNextPage();
                    }
                } else {
                    $('tr#backtotop td').show();
                    $('tr#loadmoreajaxloader td').hide();
                    TableList.bottomReached = true;
                }
                $('[data-toggle="tooltip"]').tooltip();
            }
        }));
    }
}

function resetTableList() {
    while(TableList.xhrs.length > 0) {
    TableList.xhrs.pop().abort();
    }
    TableList.currentPage = 0;
    TableList.bottomReached = false;
    $('table.tablelist .list-row').remove();
    fetchNextPage();
}

var scrolledToBottom = function() {
    return Math.abs($('.container[role=main]').scrollTop() - $('.tablelist').outerHeight(true) + $('.container[role=main]').innerHeight()) < 1;
}

$(document).ready(function() {
    TableList.currentPage = 1;
    TableList.withQuery = $(location).attr('search') && $(location).attr('search') != "";

    if ($('table.tablelist').not('.noscroll').length > 0) {
        $('.container[role=main]').scroll(function()
        {
            //Checking that we are at the bottom even if we have no integer due to zoom
            if (scrolledToBottom()) { //bottom of the scrollable container
                fetchNextPage();
            }
        });
        if ($('.tablelist').height() < $('.container[role=main]').innerHeight()) { //fetching next page to fill the document
            fetchNextPage();
        }
    }
});

if (typeof(BEHAVIORS)=="undefined") {
    BEHAVIORS = {};
}

BEHAVIORS['scrollTop'] = function() {
    $('.container[role=main]').scrollTop(0);
};

$(document).ready(function() {
    $('[data-behavior]').each(function() {
        var behavior = $(this).data('behavior');
        $(this).click(BEHAVIORS[behavior]);
    });
});
