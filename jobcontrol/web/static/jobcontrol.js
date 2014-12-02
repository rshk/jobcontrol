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

    $('.log-messages').each(function() {
        var $container = $(this),
            filter_bar = $('<div style="margin: 5px 0;"></div>');

        filter_bar.append('<strong>Min level:</strong> ');

        var filter_logs = function(level) {
            $container.find('> .message').each(function(){
                var $this = $(this),
                    _level = parseInt($this.attr('data-log-level'));
                if (_level >= level) {  // todo: can we just use .toggle(bool) ?
                    $this.show();
                }
                else {
                    $this.hide();
                }
            });
        };

        var make_link = function(cls, label, level) {
            var link = $('<a class="label label-' + cls + '" href="javascript:void(0);">' + label + '</a>');
            link.click(function(){filter_logs(level);});
            return link;
        };

        filter_bar.append(make_link('default', 'All', -1));
        filter_bar.append(' ');
        filter_bar.append(make_link('info', 'Debug', 10));
        filter_bar.append(' ');
        filter_bar.append(make_link('success', 'Info', 20));
        filter_bar.append(' ');
        filter_bar.append(make_link('warning', 'Warning', 30));
        filter_bar.append(' ');
        filter_bar.append(make_link('danger', 'Error', 40));
        filter_bar.append(' ');
        filter_bar.append(make_link('danger', 'Critical', 50));

        $container.before(filter_bar);

        // $('.log-messages > .message').each(function(){ if(parseInt($(this).attr('data-log-level')) < 30) { $(this).toggle(); } });
    });
});
