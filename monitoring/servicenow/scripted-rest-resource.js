// Reference resource: POST /api/x_boutique/alerts/upsert. Auth required.
// Configure an ACL for a dedicated integration role, a string field
// incident.u_boutique_alert_key (length 64), and a UNIQUE database index on it.
// Review business rules and close-code choices in your own instance before enabling.
(function process(request, response) {
    var data = request.body.data;
    if (!data || !/^[a-f0-9]{64}$/.test(data.key) || ['firing','resolved'].indexOf(data.status) < 0) {
        response.setStatus(400); response.setBody({error: 'Invalid alert'}); return;
    }
    var incident = new GlideRecord('incident');
    incident.addQuery('u_boutique_alert_key', data.key); incident.query();
    var exists = incident.next();
    if (data.status === 'resolved') {
        if (exists && incident.state.toString() !== '6' && incident.state.toString() !== '7') {
            incident.state = '6'; incident.close_code = 'Solved (Permanently)';
            incident.close_notes = 'Alertmanager reports this alert cycle resolved.';
            incident.update();
        }
        response.setBody({result: {status: 'resolved'}}); return;
    }
    if (!exists) {
        incident.initialize(); incident.u_boutique_alert_key = data.key;
        incident.correlation_id = data.key;
        incident.short_description = String(data.summary || 'Boutique alert').substring(0,160);
        incident.description = String(data.description || '').substring(0,4000);
        incident.impact = '2'; incident.urgency = '2';
        var id = incident.insert();
        if (!id) {
            // A concurrent insert can lose the unique-index race. Retry after its commit.
            response.setStatus(503); response.setBody({error: 'Retry upsert'}); return;
        }
    }
    response.setBody({result: {status: 'accepted'}});
})(request, response);
