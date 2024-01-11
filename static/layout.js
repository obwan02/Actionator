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
            type: 'stack',
            componentName: 'output-holder',
            content:[]
        }]
    }]
};

var layout = new GoldenLayout(config);

layout.registerComponent('action-bar', function(container, state) {
    fetch("/parts/action_bar").then(x => x.text()).then(x => container.getElement().html(x));
});

layout.registerComponent('start-form', function(container, state) {
    fetch(state.action_form_path).then(x => x.text()).then(x => {
        let elem = container.getElement();
        elem.html(x);


    });
})

layout.init();

function prepare_action(name, action_form_path) {
    layout.root.contentItems[0].contentItems[1].addChild({
        title: `Start ${name}`,
        type: 'component',
        componentName: 'start-form',
        componentState: { action_form_path }
    });
}

function start_action(form_id, action_form_path) {
    let form_data = new FormData(document.forms[form_id])
    let data = {};
    for(const [name, val] of form_data.entries()) {
        data[name] = val;
    }
    
    fetch(action_form_path, { body: JSON.stringify(data), method: "POST"}).then(x => console.debug("Data", x))
}