/**
 * Cleepbus config — Pyre connection status and recent bus activity.
 */
angular
.module('Cleep')
.directive('cleepbusConfigComponent', ['cleepbusService', '$filter',
function(cleepbusService, $filter) {

    var cleepbusConfigController = function() {
        var self = this;
        self.loading = false;
        self.status = {
            running: false,
            restart_pending: false,
            endpoint: null,
            uuid: null,
            hostname: null,
            peers_online: 0,
            peers_total: 0,
            peers: [],
            messages: [],
        };
        self.connectionComment = '';
        self.peersItems = [];
        self.messagesItems = [];

        self.$onInit = function() {
            self.refresh();
        };

        self.refresh = function() {
            self.loading = true;
            return cleepbusService.getBusStatus()
                .then(function(resp) {
                    if (resp.error) {
                        return;
                    }
                    self.status = resp.data || self.status;
                    self._render();
                })
                .finally(function() {
                    self.loading = false;
                });
        };

        self._render = function() {
            const s = self.status;
            const lines = [];
            lines.push('| | |');
            lines.push('| --- | --- |');
            lines.push(`| Status | ${s.running ? '**running**' : '**stopped**'}${s.restart_pending ? ' (restart pending)' : ''} |`);
            lines.push(`| Endpoint | \`${s.endpoint || '—'}\` |`);
            lines.push(`| Hostname | ${s.hostname || '—'} |`);
            lines.push(`| UUID | \`${s.uuid || '—'}\` |`);
            lines.push(`| Peers | ${s.peers_online || 0} online / ${s.peers_total || 0} known |`);
            self.connectionComment = lines.join('\n');

            self.peersItems = (s.peers || []).map(function(peer) {
                const host = peer.hostname || peer.uuid || 'unknown';
                const ip = peer.ip || '—';
                return {
                    title: host,
                    subtitle: `${ip}${peer.cleepdesktop ? ' · desktop' : ''} · ${peer.uuid}`,
                    icon: peer.online ? 'lan-connect' : 'lan-disconnect',
                    iconStyle: peer.online ? 'color: #2e7d32' : 'color: #9e9e9e',
                    clicks: [],
                };
            });

            self.messagesItems = (s.messages || []).map(function(entry) {
                const when = $filter('hrDatetime')(entry.ts);
                const detail = entry.detail ? ` — ${entry.detail}` : '';
                return {
                    title: `[${entry.kind}] ${entry.summary}`,
                    subtitle: when + detail,
                    icon: self._kindIcon(entry.kind),
                    clicks: [],
                };
            });
        };

        self._kindIcon = function(kind) {
            switch (kind) {
                case 'in': return 'message-arrow-left';
                case 'out': return 'message-arrow-right';
                case 'system': return 'cog';
                default: return 'cog';
            }
        };
    };

    return {
        templateUrl: 'cleepbus.config.html',
        replace: true,
        scope: true,
        controller: cleepbusConfigController,
        controllerAs: '$ctrl',
    };
}]);
