# vim: tabstop=4 shiftwidth=4 softtabstop=4
#
# Copyright 2013, Nachi Ueno, NTT I3, Inc.
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.
import mock

from neutron.openstack.common import uuidutils
from neutron.tests import base


_uuid = uuidutils.generate_uuid


class BaseDeviceDriverTestCase(base.BaseTestCase):
    FAKE_HOST = 'fake_host'

    def setUp(self, driver, patch_classes):
        super(BaseDeviceDriverTestCase, self).setUp()
        self.addCleanup(mock.patch.stopall)
        for klass in patch_classes:
            mock.patch(klass).start()
        self.execute = mock.patch(
            'neutron.agent.linux.utils.execute').start()
        self.agent = mock.Mock()
        self.driver = driver(
            self.agent,
            self.FAKE_HOST)
        self.driver.agent_rpc = mock.Mock()

    def test_vpnservice_updated(self):
        with mock.patch.object(self.driver, 'sync') as sync:
            context = mock.Mock()
            self.driver.vpnservice_updated(context)
            sync.assert_called_once_with(context, [])

    def test_create_router(self):
        process_id = _uuid()
        process = mock.Mock()
        process.vpnservice = self.FAKE_VPN_SERVICE
        self.driver.processes = {
            process_id: process}
        self.driver.create_router(process_id)
        process.enable.assert_called_once_with()

    def test_destroy_router(self):
        process_id = _uuid()
        process = mock.Mock()
        process.vpnservice = self.FAKE_VPN_SERVICE
        self.driver.processes = {
            process_id: process}
        self.driver.destroy_router(process_id)
        process.disable.assert_called_once_with()
        self.assertNotIn(process_id, self.driver.processes)

    def test_sync_removed(self):
        self.driver.agent_rpc.get_vpn_services_on_host.return_value = []
        context = mock.Mock()
        process_id = _uuid()
        process = mock.Mock()
        process.vpnservice = self.FAKE_VPN_SERVICE
        self.driver.processes = {
            process_id: process}
        self.driver.sync(context, [])
        process.disable.assert_called_once_with()
        self.assertNotIn(process_id, self.driver.processes)

    def test_sync_removed_router(self):
        self.driver.agent_rpc.get_vpn_services_on_host.return_value = []
        context = mock.Mock()
        process_id = _uuid()
        self.driver.sync(context, [{'id': process_id}])
        self.assertNotIn(process_id, self.driver.processes)
