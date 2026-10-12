/**
 * Cleepbus service — RPC helpers for bus status / debug page.
 */
angular
.module('Cleep')
.service('cleepbusService', ['rpcService',
function(rpcService) {
    const self = this;

    self.getBusStatus = function() {
        return rpcService.sendCommand('get_bus_status', 'cleepbus');
    };

    self.getPeers = function() {
        return rpcService.sendCommand('get_peers', 'cleepbus');
    };
}]);
