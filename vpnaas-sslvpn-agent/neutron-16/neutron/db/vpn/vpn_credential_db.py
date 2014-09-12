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
import hashlib
from sqlalchemy.orm import exc
import uuid

from neutron.common import exceptions as q_exc
from neutron.db import db_base_plugin_v2 as base_db
from neutron.db.vpn import vpn_db
from neutron.extensions.vpncredential import VPNCredentialPluginBase


class VPNCredentialNotFound(q_exc.NotFound):
    message = _("Credential %(credential_id)s could not be found")


class VPNCredential_db_mixin(VPNCredentialPluginBase,
                             base_db.CommonDbMixin):

    def create_vpn_credential(self, context, vpn_credential):
        credential = vpn_credential['vpn_credential']
        tenant_id = self._get_tenant_id_for_create(context, credential)
        with context.session.begin(subtransactions=True):
            credential_db = vpn_db.VPNCredential(
                id=str(uuid.uuid4()),
                tenant_id=tenant_id,
                name=credential['name'],
                ca=credential['ca'],
                server_certificate=credential['server_certificate'],
                server_key=credential['server_key'],
                dh=credential['dh'],
                crl=credential['crl'],
            )
            context.session.add(credential_db)

        credential_db = self._get_resource(
            context,
            vpn_db.VPNCredential,
            credential_db['id'])
        return self._make_vpn_credential_dict(credential_db)

    def get_vpn_credentials(self, context, filters=None, fields=None):
        return self._get_collection(context, vpn_db.VPNCredential,
                                    self._make_vpn_credential_dict,
                                    filters=filters, fields=fields)

    def _make_vpn_credential_dict(self,
                                  credential,
                                  fields=None):
        res = {
            'id': credential['id'],
            'tenant_id': credential['tenant_id'],
            'name': credential['name'],
            'ca': credential['ca'],
            'server_certificate': credential['server_certificate'],
            'server_key': hashlib.sha256(credential['server_key']).hexdigest(),
            'dh': credential['dh'],
            'crl': credential['crl'],
        }
        return self._fields(res, fields)

    def get_vpn_credential(self, context, id, fields=None):
        try:
            credential = self._get_resource(context, vpn_db.VPNCredential, id)
        except exc.NoResultFound:
            raise vpn_db.VPNCredentialNotFound(credential_id=id)
        return self._make_vpn_credential_dict(credential, fields)

    def _update_vpn_credential(self, context, id, credential):
        with context.session.begin(subtransactions=True):
            credential_db = self._get_resource(
                context,
                vpn_db.VPNCredential,
                id)
            if credential:
                credential_db.update(credential)
        return credential_db

    def update_vpn_credential(self, context, id, credential_in):
        credential = credential_in['credential']
        res = self._update_vpn_credential(context, id, credential)
        return self._make_vpn_credential_dict(res)

    def delete_vpn_credential(self, context, id):
        with context.session.begin(subtransactions=True):
            credential_db = self._get_resource(
                context,
                vpn_db.VPNCredential,
                id)
            context.session.delete(credential_db)
