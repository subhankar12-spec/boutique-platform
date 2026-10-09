// Reference resource: POST /api/x_boutique/alerts/upsert. Authentication required.
// Prerequisites: dedicated integration role/ACL; x_boutique_alert_cycle table with
// u_key string(64), u_status choice(firing/resolved), u_revision integer, UNIQUE u_key;
// incident.u_boutique_alert_key string(64) with UNIQUE index. Keep lifecycle rows:
// they are tombstones that prevent a delayed firing request reopening a resolved cycle.
// Validate business rules and concurrent request behavior in your developer instance.
(function process(request, response) {
    var data = request.body.data;
    function fail(code, message) { response.setStatus(code); response.setBody({error: message}); }
    if (!data || !/^[a-f0-9]{64}$/.test(data.key) || ['firing','resolved'].indexOf(data.status) < 0 ||
            typeof data.revision !== 'number' || !isFinite(data.revision) || Math.floor(data.revision) !== data.revision || data.revision < 1) {
        fail(400, 'Invalid alert'); return;
    }
    function cycle() {
        var row = new GlideRecord('x_boutique_alert_cycle');
        row.addQuery('u_key', data.key); row.query();
        return row.next() ? row : null;
    }
    var record = cycle();
    if (!record) {
        record = new GlideRecord('x_boutique_alert_cycle'); record.initialize();
        record.u_key = data.key; record.u_status = data.status; record.u_revision = data.revision;
        if (!record.insert()) { fail(503, 'Retry lifecycle upsert'); return; }
    } else if (record.u_status.toString() !== 'resolved') {
        // Conditional update preserves terminal resolution during concurrent delivery.
        var change = new GlideRecord('x_boutique_alert_cycle');
        change.addQuery('u_key', data.key); change.addQuery('u_status', '!=', 'resolved');
        change.addQuery('u_revision', '<', data.revision);
        change.setValue('u_status', data.status); change.setValue('u_revision', data.revision);
        change.updateMultiple();
    }
    record = cycle();
    if (!record) { fail(503, 'Retry lifecycle lookup'); return; }
    var resolved = record.u_status.toString() === 'resolved';
    var incident = new GlideRecord('incident');
    incident.addQuery('u_boutique_alert_key', data.key); incident.query();
    var exists = incident.next();
    if (!resolved && !exists) {
        incident.initialize(); incident.u_boutique_alert_key = data.key;
        incident.correlation_id = data.key;
        incident.short_description = String(data.summary || 'Boutique alert').substring(0,160);
        incident.description = String(data.description || '').substring(0,4000);
        incident.impact = '2'; incident.urgency = '2';
        if (!incident.insert()) { fail(503, 'Retry incident upsert'); return; }
        // A concurrent resolution may have arrived while the incident was inserted.
        record = cycle(); resolved = record && record.u_status.toString() === 'resolved';
        exists = true;
    }
    if (resolved && exists && incident.state.toString() !== '6' && incident.state.toString() !== '7') {
        incident.state = '6'; incident.close_code = 'Solved (Permanently)';
        incident.close_notes = 'Alertmanager reports this alert cycle resolved.';
        if (!incident.update()) { fail(503, 'Retry resolution'); return; }
    }
    response.setBody({result: {status: resolved ? 'resolved' : 'accepted'}});
})(request, response);
