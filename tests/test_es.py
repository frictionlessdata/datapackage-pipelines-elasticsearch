import os
import unittest
import datetime

from datapackage_pipelines.utilities.lib_test_helpers import mock_processor_test

from elasticsearch import Elasticsearch

import datapackage_pipelines_elasticsearch.processors

import logging


class TestToIndexProcessor(unittest.TestCase):

    def setUp(self):
        self.bucket = 'my.test.bucket'
        self.resources = [{
            'name': 'resource',
            "format": "csv",
            "path": "data/test.csv",
            "schema": {
                "fields": [
                    {
                        "name": "Date",
                        "type": "date",
                    },
                    {
                        "name": "Name",
                        "type": "string",
                    }
                ],
                'primaryKey': ['Name']
            }
        }]
        self.datapackage = {
            'owner': 'me',
            'name': 'my-datapackage',
            'project': 'my-project',
            'resources': self.resources
        }
        self.params = {
            'engine': 'localhost:9200',
            'indexes': {
                'dummy': [{
                    'resource-name': 'resource',
                    'doc-type': 'dummydoc'
                }]
            }
        }
        # Path to the processor we want to test
        self.processor_dir = \
            os.path.dirname(__file__)
        self.processor_path = os.path.join(self.processor_dir, 'dummy_processor.py')

    def test_index(self):
        # Should be in setup but requires mock
        class TempList(list):
            pass

        res = TempList([{'Date': datetime.datetime(2001, 2, 3), 'Name': 'Name'}])
        res.spec = self.resources[0]
        res_iter = [res]

        spew_args = mock_processor_test(self.processor_path,
                                        (self.params,
                                         self.datapackage,
                                         res_iter))

        spew_res_iter = spew_args[0][1]
        # We need to actually read the rows to execute the iterator(s)
        rows = [list(res) for res in spew_res_iter]

        Elasticsearch().indices.flush()
        records = Elasticsearch().search(index='dummy')
        records = [r['_source'] for r in records['hits']['hits']]

        assert records == [{'Date': '2001-02-03T00:00:00', 'Name': 'Name'}]
