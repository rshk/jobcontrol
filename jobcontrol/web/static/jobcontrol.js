// Javascript for JobControl

var JobControl = {};

// Autocomplete / documentation for functions
JobControl.FunctionAutocomplete = function(input, docs_container){
    var ac_timeout = null;

    $(input).attr('autocomplete', 'off');
    $(docs_container).html('Autocomplete not implemented yet');

    // var update_completions = function() {
    //     $(docs_container).append('Updated on ' + (new Date()) + '<br>');
    // };

    // $(input).bind('keyup', function(evt) {
    //  if (ac_timeout !== null) {
    //         clearTimeout(ac_timeout);
    //  }
    //  ac_timeout = setTimeout(update_completions, 300);
    // });

};
