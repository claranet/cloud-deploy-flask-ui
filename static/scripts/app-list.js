if (typeof(BEHAVIORS)=="undefined") {
    BEHAVIORS = {};
}

BEHAVIORS['role'] = function(){
    var role = $(this).data('role');
    setTableListRole(role);
};
BEHAVIORS['env'] = function() {
    var env = $(this).data('env');
    setTableListEnv(env);
};

var getUrlParameter = function getUrlParameter(sParam, sDefault) {
    var sPageURL = decodeURIComponent(window.location.search.substring(1)),
        sURLVariables = sPageURL.split('&'),
        sParameterName,
        i;

    for (i = 0; i < sURLVariables.length; i++) {
        sParameterName = sURLVariables[i].split('=');

        if (sParameterName[0] === sParam) {
            return sParameterName[1] === undefined ? true : sParameterName[1];
        }
    }
    return sDefault;
};

function ParseQueryString() {
    var getQueryStringNameValuePairs = new Array();
    var queryString = window.location.search.substring(1);

    var nameValuePairs = queryString.split(/&/);

    
    for (var i in nameValuePairs) {
        var nameValue = nameValuePairs[i].split(/=/);
        getQueryStringNameValuePairs[nameValue[0]] = nameValue[1];
    }
    return getQueryStringNameValuePairs;
}

var tableListParameters = ParseQueryString();

function setTableListEnv(value) {
    if(value == '*') {
        value = undefined;
    }
    tableListParameters.env = value;
    updateQueryString();
    resetTableList();
}

function setTableListRole(value) {
    tableListParameters.role = value;
    $('.dropdown-toggle').html((value ? value : 'Role') + '<span class="caret"></span>');
    updateQueryString();
    resetTableList();
}

function updateQueryString() {
    queryString = new URI("?");
    for(key in tableListParameters) {
        queryString.addFragment(key, tableListParameters[key]);
    }
    queryString = (queryString+"").substring(1);
    uri = window.location.toString();
    uri = uri.substring(0, uri.indexOf("?"));
    window.history.pushState(null, null, uri + queryString);
}

function setTableListName() {
    var searchValue = $('#global-search input').val();
    if(searchValue == '') {
        searchValue = undefined;
    }
    tableListParameters.name = searchValue;
    updateQueryString();
    resetTableList();
}

scrolledToBottom = function() {
    return Math.abs($('.container[role=main]').scrollTop() - $('#tabbed-apps').outerHeight(true) + $('.container[role=main]').innerHeight()) < 1;
}

$(document).ready(function() {
    $('#global-search').focusin(function () {
        $('#global-search').addClass('expanded');
    });
    $('#global-search').focusout(function () {
        $('#global-search').removeClass('expanded');
    });
    $('#global-search button').click(function (evt) {
        evt.preventDefault();
        setTableListName();
    });
    $('#global-search input').keypress(function (e) {
        if (e.which == 13) {
            setTableListName();
            return false;  
        }
    });
    $('#global-search input').val(getUrlParameter('name'));

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
