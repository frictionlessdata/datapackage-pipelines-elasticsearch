import datetime
import decimal
import os

import logging
from elasticsearch import Elasticsearch
from tableschema_elasticsearch import Storage

from datapackage_pipelines.utilities.extended_json import LazyJsonLine
from datapackage_pipelines.lib.dump.dumper_base import DumperBase


def normalize(obj):
    if isinstance(obj, (dict, LazyJsonLine)):
        return dict(
            (k, normalize(v))
            for k, v in obj.items()
        )
    elif isinstance(obj, (str, int, float, bool, datetime.date)):
        return obj
    elif isinstance(obj, decimal.Decimal):
        return float(obj)
    elif isinstance(obj, (list, set)):
        return [normalize(x) for x in obj]
    elif obj is None:
        return None
    assert False, "Don't know how to handle object (%s) %r" % (type(obj), obj)


class ESDumper(DumperBase):

    def __init__(self, mapper_cls=None):
        super(ESDumper, self).__init__()
        self.mapper_cls = mapper_cls

    def initialize(self, parameters):
        super(ESDumper, self).initialize(parameters)
        self.index_to_resource = parameters['indexes']
        engine = parameters.get('engine', 'env://DPP_ELASTICSEARCH')
        if engine.startswith('env://'):
            env_var = engine[6:]
            engine = os.environ.get(env_var)
            assert engine is not None, \
                "Couldn't connect to ES Instance - " \
                "Please set your '%s' environment variable" % env_var
        self.engine = Elasticsearch(hosts=[engine])
        try:
            if not self.engine.ping():
                logging.exception('Failed to connect to database %s', engine)
        except Exception:
            logging.exception('Failed to connect to database %s', engine)
            raise

        self.converted_resources = {}
        for k, v in self.index_to_resource.items():
            for w in v:
                w['index-name'] = k
                self.converted_resources[w['resource-name']] = w

    def handle_resource(self, resource, spec, parameters, datapackage):
        resource_name = spec['name']
        if resource_name not in self.converted_resources:
            return resource
        else:
            primary_key = spec['schema']['primaryKey']
            converted_resource = self.converted_resources[resource_name]
            index_name = converted_resource['index-name']
            doc_type = converted_resource['doc-type']
            storage = Storage(self.engine)
            storage.create(index_name, [(doc_type, spec['schema'])],
                           always_recreate=False, mapping_generator_cls=self.mapper_cls)
            logging.info('Writing to ES %s -> %s/%s',
                         resource_name, index_name, doc_type)

            def normalizer(rows):
                for row in rows:
                    yield normalize(row)

            return storage.write(index_name, doc_type, normalizer(resource),
                                 primary_key, as_generator=True)


if __name__ == '__main__':
    ESDumper()()
