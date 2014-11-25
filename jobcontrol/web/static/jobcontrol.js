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


// Collapsible things
$(function(){
    $('[data-toggle]').each(function(){
        var $this = $(this),
            selector = $this.data('toggle'),
            elem = $(selector),
            default_ = $this.data('toggle-default'),
            icon_up = 'fa fa-toggle-right',
            icon_down = 'fa fa-toggle-down';

        $this.click(function(){
            elem.toggle();
            if (elem.is(':hidden')) {
                $($this.find('.toggle-indicator')).attr('class', 'toggle-indicator ' + icon_up);
            }
            else {
                $($this.find('.toggle-indicator')).attr('class', 'toggle-indicator ' + icon_down);
            }
        });

        $($this.find('.toggle-indicator')).attr('class', 'toggle-indicator ' + icon_down);
        if (default_ === 'hidden') {
            elem.hide();
            $($this.find('.toggle-indicator')).attr('class', 'toggle-indicator ' + icon_up);
        }
    });
});
