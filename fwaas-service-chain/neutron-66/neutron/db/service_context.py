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
# @author: Rajesh Mohan, rajesh_mohan3@dell.com, DELL, Inc.

import sqlalchemy as sa
from sqlalchemy import orm
from sqlalchemy.orm import exc

from neutron.api.v2 import attributes
from neutron.common import constants
from neutron.common import exceptions as qexception
from neutron.db import l3_db
from neutron.db import model_base
from neutron.db import models_v2
from neutron.openstack.common import log as logging
from neutron.openstack.common import uuidutils


LOG = logging.getLogger(__name__)


# Service Context Exceptions
class ServiceContextNotSupported(qexception.Invalid):
    message = _("Service Context %(id) not supported.")


class ServiceContextNotFound(qexception.NotFound):
    message = _("Service Context %(id) could not be found.")


class NetworkContextNotFound(qexception.NotFound):
    message = _("Network Context %(id)s could not be found.")


class SubnetContextNotFound(qexception.NotFound):
    message = _("Subnet Context %(id)s could not be found.")


class PortContextNotFound(qexception.NotFound):
    message = _("Port Context %(id)s could not be found.")


class RouterContextNotFound(qexception.NotFound):
    message = _("Router Context %(id)s could not be found.")


class ServiceContextInUse(qexception.InUse):
    message = _("Service Context %(id)s is still in use.")


class NetworkInUseByNetworkContext(qexception.InUse):
    message = _("Network %(id)s in use by NetworkContext %(context_id)s.")


class SubnetInUseBySubnetContext(qexception.InUse):
    message = _("Subnet %(id)s in use by SubnetContext %(context_id)s.")


class PortInUseByPortContext(qexception.InUse):
    message = _("Port %(id)s in use by PortContext %(context_id)s.")


class RouterInUseByRouterContext(qexception.InUse):
    message = _("Router %(id)s in use by RouterContext %(context_id)s.")


class NetworkContext(model_base.BASEV2, models_v2.HasId):
    """Represents a Network Context for service insertion."""
    __tablename__ = 'si_network_contexts'
    service_context_id = sa.Column(sa.String(36),
                                   sa.ForeignKey('service_context.id',
                                                 ondelete='CASCADE'),
                                   nullable=False,
                                   unique=False)
    network_id = sa.Column(sa.String(36),
                           sa.ForeignKey('networks.id', ondelete='CASCADE'),
                           nullable=False,
                           unique=False)
    network = orm.relationship(models_v2.Network,
                               backref=orm.backref("si_network_contexts",
                                                   lazy='joined',
                                                   uselist=False,
                                                   cascade='delete'))


class SubnetContext(model_base.BASEV2, models_v2.HasId):
    """Represents a Subnet Context for service insertion."""
    __tablename__ = 'si_subnet_contexts'
    service_context_id = sa.Column(sa.String(36),
                                   sa.ForeignKey('service_context.id',
                                                 ondelete='CASCADE'),
                                   nullable=False,
                                   unique=False)
    subnet_id = sa.Column(sa.String(36),
                          sa.ForeignKey('subnets.id', ondelete='CASCADE'),
                          nullable=False,
                          unique=False)
    subnet = orm.relationship(models_v2.Subnet,
                              backref=orm.backref("si_subnet_contexts",
                                                  lazy='joined',
                                                  uselist=False,
                                                  cascade='delete'))


class PortContext(model_base.BASEV2, models_v2.HasId):
    """Represents a Port Context for service insertion."""
    __tablename__ = 'si_port_contexts'
    service_context_id = sa.Column(sa.String(36),
                                   sa.ForeignKey('service_context.id',
                                                 ondelete='CASCADE'),
                                   nullable=False,
                                   unique=False)
    port_id = sa.Column(sa.String(36),
                        sa.ForeignKey('ports.id', ondelete='CASCADE'),
                        nullable=False,
                        unique=False)
    port = orm.relationship(models_v2.Port,
                            backref=orm.backref("si_port_contexts",
                                                lazy='joined',
                                                uselist=False,
                                                cascade='delete'))


class RouterContext(model_base.BASEV2, models_v2.HasId):
    """Represents a Router Context for service insertion."""
    __tablename__ = 'si_router_contexts'
    service_context_id = sa.Column(sa.String(36),
                                   sa.ForeignKey('service_context.id',
                                                 ondelete='CASCADE'),
                                   nullable=False,
                                   unique=False)
    router_id = sa.Column(sa.String(36),
                          sa.ForeignKey('routers.id', ondelete='CASCADE'),
                          nullable=False, unique=False)
    router = orm.relationship(l3_db.Router,
                              backref=orm.backref("si_router_contexts",
                                                  lazy='joined',
                                                  uselist=False,
                                                  cascade='delete'))


class ServiceContext(model_base.BASEV2, models_v2.HasId):
    """Represents a Service Context."""
    __tablename__ = 'service_context'

    networks = orm.relationship(NetworkContext,
                                backref=orm.backref("service_context",
                                                    cascade='all, delete'))
    subnets = orm.relationship(SubnetContext,
                               backref=orm.backref("service_context",
                                                   cascade='all, delete'))
    ports = orm.relationship(PortContext,
                             backref=orm.backref("service_context",
                                                 cascade='all, delete'))
    routers = orm.relationship(RouterContext,
                               backref=orm.backref("service_context",
                                                   cascade='all, delete'))


class ServiceContextMixin(object):
    """Mixin class for Service Context DB implementation."""
    context_class_map = {
        'service': ServiceContext,
        'network': NetworkContext,
        'subnet': SubnetContext,
        'port': PortContext,
        'router': RouterContext
    }
    context_exc_notfound_map = {
        'service': ServiceContextNotFound,
        'network': NetworkContextNotFound,
        'subnet': SubnetContextNotFound,
        'port': PortContextNotFound,
        'router': RouterContextNotFound
    }
    context_exc_inuse_map = {
        'service': ServiceContextInUse,
        'network': NetworkInUseByNetworkContext,
        'subnet': SubnetInUseBySubnetContext,
        'port': PortInUseByPortContext,
        'router': RouterInUseByRouterContext
    }

    def _get_resource_context(self, context, id, resource):
        try:
            return self._get_by_id(context, self.context_class_map[resource],
                                   id)
        except exc.NoResultFound:
            raise self.context_exc_notfound_map[resource](id=id)

    def _get_resource_contexts(self, context, res_id, resource):
        res_id_name = "%s_id" % resource
        filters = {res_id_name: [res_id]}
        return self._get_collection_query(context,
                                          self.context_class_map[resource],
                                          filters=filters)

    def _make_service_context_dict(self, svc_ctxt, fields=None):
        res = {'service_context_id': svc_ctxt['id']}
        return self._fields(res, fields)

    def _get_resource_by_service_context(self, context, svc_ctxt_id,
                                         resource):
        query = context.session.query(self.context_class_map[resource])
        return query.filter_by(service_context_id=svc_ctxt_id).all()

    def _process_service_context(self, context, service_data):
        LOG.debug(_("_process_service_context() called"))
        if not attributes.is_attr_set(service_data.get('service_context')):
            return
        sctxt = service_data['service_context']
        if not sctxt:
            return

        with context.session.begin(subtransactions=True):
            service_context_db = ServiceContext(id=uuidutils.generate_uuid())
            context.session.add(service_context_db)

        for resource in constants.SI_SUPPORTED_RESOURCE_TYPES:
            if attributes.is_attr_set(sctxt.get(resource)):
                self._process_resource_context(context, service_context_db,
                                               sctxt[resource], resource)
        return service_context_db

    def _process_resource_context(self, context, service_context_db, res_list,
                                  resource):
        LOG.debug(_("_process_resource_context() called"))
        res_id_name = "%s_id" % resource[0:-1]
        for res_id in res_list:
            with context.session.begin(subtransactions=True):
                args = {'id': uuidutils.generate_uuid(),
                        'service_context_id': service_context_db.id,
                        res_id_name: res_id}
                res_db = self.context_class_map[resource[0:-1]](**args)
                context.session.add(res_db)

    def _delete_service_context(self, context, id):
        LOG.debug(_("_process_service_context() called"))
        with context.session.begin(subtransactions=True):
            query = context.session.query(
                ServiceContext).with_lockmode('update')
            service_context_db = query.filter_by(id=id).one()
            for resource in constants.SI_SUPPORTED_RESOURCE_TYPES:
                self._delete_resource_context(context,
                                              service_context_db,
                                              resource)
            context.session.delete(service_context_db)

    def _delete_resource_context(self, context, service_context_db,
                                 resource):
        LOG.debug(_("_delete_resource_context() called"))
        with context.session.begin(subtransactions=True):
            query = context.session.query(
                self.context_class_map[resource[0:-1]]).with_lockmode(
                    'update')
            try:
                res_db = query.filter_by(
                    service_context_id=service_context_db.id).one()
                context.session.delete(res_db)
            except exc.NoResultFound:
                pass

    def get_service_context(self, context, id, fields=None):
        LOG.debug(_("get_service_context() called"))
        service_context = self._get_resource_context(context, id, 'service')
        svc_ctxt_dict = self._make_service_context_dict(service_context,
                                                        fields)
        for resource in constants.SI_SUPPORTED_RESOURCE_TYPES:
            res_ctxts = self._get_resource_by_service_context(
                context, id, resource[0:-1])
            res_id = '%s_id' % resource[0:-1]
            svc_ctxt_dict[resource] = ([res_ctxt[res_id] for res_ctxt in
                                       res_ctxts])
        return svc_ctxt_dict

    def check_resource_in_use(self, context, res_id, resource):
        LOG.debug(_("check_resource_in_use() called"))
        resource_context = self._get_resource_contexts(context, res_id,
                                                       resource)
        if resource_context.count():
            raise self.context_exc_inuse_map[resource](
                id=res_id, context_id=resource_context[0].id)
