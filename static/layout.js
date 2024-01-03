var config = {
    content: [{
        type: 'row',
        content:[{
            type: 'component',
            title: "Actions",
            width: 20,
            componentName: 'action-bar',
            isClosable: false,
        },{
            type: 'column',
            content:[{
                type: 'component',
                componentName: 'output',
                componentState: { func_name: null }
            }]
        }]
    }]
};

var layout = new GoldenLayout(config);

layout.registerComponent('action-bar', function(container, state) {
    fetch("/static/gen/action_bar.html").then(x => x.text()).then(x => container.getElement().html(x));
});

layout.registerComponent('output', function(container, state) {
    container.getElement().html("<code>TODO</code>");
});

layout.init();
