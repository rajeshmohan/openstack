# Copyright 2014
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
#
# @author: Rajesh Mohan, Rajesh_Mohan3@Dell.com, DELL Inc.

import copy

import mock
from oslo.config import cfg
from webob import exc
import webtest

from neutron.api import extensions
from neutron.api.v2 import attributes
from neutron.common import config
from neutron.extensions import vpncredential
from neutron import manager
from neutron.openstack.common import uuidutils
from neutron.plugins.common import constants
from neutron import quota
from neutron.tests.unit import test_api_v2
from neutron.tests.unit import test_extensions
from neutron.tests.unit import testlib_api


_uuid = uuidutils.generate_uuid
_get_path = test_api_v2._get_path


class VpncredentialTestExtensionManager(object):

    def get_resources(self):
        # Add the resources to the global attribute map
        # This is done here as the setup process won't
        # initialize the main API router which extends
        # the global attribute map
        attributes.RESOURCE_ATTRIBUTE_MAP.update(
            vpncredential.RESOURCE_ATTRIBUTE_MAP)
        return vpncredential.Vpncredential.get_resources()

    def get_actions(self):
        return []

    def get_request_extensions(self):
        return []


class VpncredentialExtensionTestCase(testlib_api.WebTestCase):
    fmt = 'json'

    def setUp(self):
        super(VpncredentialExtensionTestCase, self).setUp()
        plugin = 'neutron.extensions.vpncredential.VPNCredentialPluginBase'
        # Ensure 'stale' patched copies of the plugin are never returned
        manager.NeutronManager._instance = None

        # Ensure existing ExtensionManager is not used
        extensions.PluginAwareExtensionManager._instance = None

        # Create the default configurations
        args = ['--config-file', test_api_v2.etcdir('neutron.conf.test')]
        config.parse(args)

        #just stubbing core plugin with LoadBalancer plugin
        cfg.CONF.set_override('core_plugin', plugin)
        cfg.CONF.set_override('service_plugins', [plugin])

        self._plugin_patcher = mock.patch(plugin, autospec=True)
        self.plugin = self._plugin_patcher.start()
        instance = self.plugin.return_value
        instance.get_plugin_type.return_value = constants.VPN

        ext_mgr = VpncredentialTestExtensionManager()
        self.ext_mdw = test_extensions.setup_extensions_middleware(ext_mgr)
        self.api = webtest.TestApp(self.ext_mdw)
        super(VpncredentialExtensionTestCase, self).setUp()

        quota.QUOTAS._driver = None
        cfg.CONF.set_override('quota_driver', 'neutron.quota.ConfDriver',
                              group='QUOTAS')

    def tearDown(self):
        self._plugin_patcher.stop()
        self.api = None
        self.plugin = None
        cfg.CONF.reset()
        super(VpncredentialExtensionTestCase, self).tearDown()

    def test_vpn_credential_create(self):
        """Test case to create an vpn_credential."""
        vpn_credential_id = _uuid()
        data = {'vpn_credential': {
            'name': 'cred1',
            'ca': 'CA certificate string',
            'server_certificate': 'Server certificate string',
            'server_key': 'Server key string',
            'dh': 'DH in PEM format',
            'crl': 'CRL in PEM format',
            'tenant_id': _uuid()}}

        return_value = copy.copy(data['vpn_credential'])
        return_value.update({'id': vpn_credential_id})

        instance = self.plugin.return_value
        instance.create_vpn_credential.return_value = return_value
        res = self.api.post(_get_path('vpn/vpn-credentials', fmt=self.fmt),
                            self.serialize(data),
                            content_type='application/%s' % self.fmt)
        instance.create_vpn_credential.assert_called_with(
            mock.ANY, vpn_credential=data)
        self.assertEqual(res.status_int, exc.HTTPCreated.code)
        res = self.deserialize(res)
        self.assertIn('vpn_credential', res)
        self.assertEqual(res['vpn_credential'], return_value)

    def test_vpn_credential_list(self):
        """Test case to list all vpn credential."""
        vpn_credential_id = _uuid()

        return_value = [{'name': 'cred1',
                         'ca': 'CA certificate string',
                         'server_certificate': 'Server certificate string',
                         'server_key': 'Server key string',
                         'dh': 'DH in PEM format',
                         'crl': 'CRL in PEM format',
                         'tenant_id': _uuid(),
                         'id': vpn_credential_id}]
        instance = self.plugin.return_value
        instance.get_vpn_credentials.return_value = return_value

        res = self.api.get(_get_path('vpn/vpn-credentials', fmt=self.fmt))

        instance.get_vpn_credentials.assert_called_with(
            mock.ANY, fields=mock.ANY, filters=mock.ANY)
        self.assertEqual(res.status_int, exc.HTTPOk.code)

    def test_vpn_credential_update(self):
        """Test case to update an vpn_credential."""
        vpn_credential_id = _uuid()
        cred_data = {'name': 'cred2',
                     'dh': 'New DH value'}
        update_data = {'vpn_credential': cred_data}
        return_value = {'name': 'cred2',
                        'ca': 'CA certificate string',
                        'server_certificate': 'Server certificate string',
                        'server_key': 'Server key string',
                        'dh': 'New DH value',
                        'crl': 'CRL in PEM format',
                        'tenant_id': _uuid(),
                        'id': vpn_credential_id}
        instance = self.plugin.return_value
        instance.update_vpn_credential.return_value = return_value

        res = self.api.put(_get_path('vpn/vpn-credentials',
                                     id=vpn_credential_id,
                                     fmt=self.fmt),
                           self.serialize(update_data))

        instance.update_vpn_credential.assert_called_with(
            mock.ANY, vpn_credential_id, vpn_credential=update_data)
        self.assertEqual(res.status_int, exc.HTTPOk.code)
        res = self.deserialize(res)
        self.assertIn('vpn_credential', res)
        self.assertEqual(res['vpn_credential'], return_value)

    def test_vpn_credential_get(self):
        """Test case to get or show an vpn_credential."""
        vpn_credential_id = _uuid()
        return_value = {'name': 'cred1',
                        'ca': 'CA certificate string',
                        'server_certificate': 'Server certificate string',
                        'server_key': 'Server key string',
                        'dh': 'DH in PEM format',
                        'crl': 'CRL in PEM format',
                        'tenant_id': _uuid(),
                        'id': vpn_credential_id}
        instance = self.plugin.return_value
        instance.get_vpn_credential.return_value = return_value

        res = self.api.get(_get_path('vpn/vpn-credentials',
                                     id=vpn_credential_id,
                                     fmt=self.fmt))

        instance.get_vpn_credential.assert_called_with(mock.ANY,
                                                       vpn_credential_id,
                                                       fields=mock.ANY)
        self.assertEqual(res.status_int, exc.HTTPOk.code)
        res = self.deserialize(res)
        self.assertIn('vpn_credential', res)
        self.assertEqual(res['vpn_credential'], return_value)

    def test_vpn_credential_delete(self):
        """Test case to delete an vpn_credential."""
        vpn_credential_id = _uuid()
        res = self.api.delete(_get_path('vpn/vpn-credentials',
                                        id=vpn_credential_id,
                                        fmt=self.fmt))
        instance = self.plugin.return_value
        instance.delete_vpn_credential.assert_called_with(
            mock.ANY, vpn_credential_id)
        self.assertEqual(res.status_int, exc.HTTPNoContent.code)


class VpncredentialExtensionTestCaseXML(VpncredentialExtensionTestCase):
    fmt = 'xml'
