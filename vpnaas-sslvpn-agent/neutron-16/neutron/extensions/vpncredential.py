# vim: tabstop=4 shiftwidth=4 softtabstop=4
#
# Copyright 2013 OpenStack Foundation.
# All Rights Reserved.
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#         http://www.apache.org/licenses/LICENSE-2.0
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

import abc

import six

from neutron.api import extensions
from neutron.api.v2 import attributes as attr
from neutron.api.v2 import resource_helper
from neutron.plugins.common import constants
from neutron.services.service_base import ServicePluginBase


RESOURCE_ATTRIBUTE_MAP = {
    'vpn_credentials': {
        'id': {'allow_post': False, 'allow_put': False,
               'validate': {'type:uuid': None},
               'is_visible': True,
               'primary_key': True},
        'tenant_id': {'allow_post': True, 'allow_put': False,
                      'validate': {'type:string': None},
                      'required_by_policy': True,
                      'is_visible': True},
        'name': {
            'allow_post': True,
            'allow_put': True,
            'default': '',
            'validate': {'type:string': None},
            'is_visible': True},
        'ca': {
            'allow_post': True,
            'allow_put': True,
            'validate': {'type:string': None},
            'is_visible': True},
        'server_certificate': {
            'allow_post': True,
            'allow_put': True,
            'validate': {'type:string': None},
            'is_visible': True},
        'server_key': {
            'allow_post': True,
            'allow_put': True,
            'validate': {'type:string': None},
            'is_visible': True},
        'dh': {
            'allow_post': True,
            'allow_put': True,
            'validate': {'type:string': None},
            'default': '',
            'is_visible': True},
        'crl': {
            'allow_post': True,
            'allow_put': True,
            'default': '',
            'validate': {'type:string': None},
            'is_visible': True}
    }
}


class Vpncredential(extensions.ExtensionDescriptor):

    @classmethod
    def get_name(cls):
        return "VPNCredential extension"

    @classmethod
    def get_alias(cls):
        return "vpncredential"

    @classmethod
    def get_description(cls):
        return "Extension for VPNCredential"

    @classmethod
    def get_namespace(cls):
        return "http://wiki.openstack.org/Neutron/vpncredential/API_1.0"

    @classmethod
    def get_updated(cls):
        return "2013-10-07T10:00:00-00:00"

    @classmethod
    def get_resources(cls):
        plural_mappings = resource_helper.build_plural_mappings(
            {}, RESOURCE_ATTRIBUTE_MAP)
        attr.PLURALS.update(plural_mappings)
        return resource_helper.build_resource_info(plural_mappings,
                                                   RESOURCE_ATTRIBUTE_MAP,
                                                   constants.VPN,
                                                   register_quota=True,
                                                   translate_name=True)

    @classmethod
    def get_plugin_interface(cls):
        return VPNCredentialPluginBase

    def update_attributes_map(self, attributes):
        super(Vpncredential, self).update_attributes_map(
            attributes, extension_attrs_map=RESOURCE_ATTRIBUTE_MAP)

    def get_extended_resources(self, version):
        if version == "2.0":
            return RESOURCE_ATTRIBUTE_MAP
        else:
            return {}


@six.add_metaclass(abc.ABCMeta)
class VPNCredentialPluginBase(ServicePluginBase):

    def get_plugin_name(self):
        return constants.VPN

    def get_plugin_type(self):
        return constants.VPN

    def get_plugin_description(self):
        return 'VPNCredential plugin'

    @abc.abstractmethod
    def create_vpn_credential(self, context, vpn_credential):
        pass

    @abc.abstractmethod
    def get_vpn_credentials(self, context, filters=None, fields=None):
        pass

    @abc.abstractmethod
    def get_vpn_credential(self, context, id, fields=None):
        pass

    @abc.abstractmethod
    def update_vpn_credential(self, context, id, vpn_credential):
        pass

    @abc.abstractmethod
    def delete_vpn_credential(self, context, id):
        pass
