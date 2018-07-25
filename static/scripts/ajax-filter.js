function parseQueryString() {
    var getQueryStringNameValuePairs = new Array();
    var queryString = window.location.search.substring(1);

    var nameValuePairs = queryString.split(/&/);

    
    for (var i in nameValuePairs) {
        var nameValue = nameValuePairs[i].split(/=/);
        getQueryStringNameValuePairs[nameValue[0]] = nameValue[1];
    }
    return getQueryStringNameValuePairs;
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

var tableListParameters = parseQueryString();

$("form.filter-form").submit(function(event) {
    event.preventDefault();

    var values = $(this).serializeArray();
    values.forEach(function(value) {
        tableListParameters[value.name] = value.value;
    });

    updateQueryString();
    resetTableList();
});