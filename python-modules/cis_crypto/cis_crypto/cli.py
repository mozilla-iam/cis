#!/usr/bin/env python3
import argparse
import jose
import logging
import sys

from cis_crypto import common
from cis_crypto import get_config
from cis_crypto import operation


class cli():
    def __init__(self):
        self.config = None
        self.prog = sys.argv[0].split('/')[-1]

    def parse_args(self, args):
        parser = argparse.ArgumentParser(
            description="""
            Command line wrapper for mozilla-iam sign verify/operations of JSON and YAML using JWKS.
            """
        )

        subparsers = parser.add_subparsers(dest='cryptographic-operation')
        subparsers.required = True

        sign_operation_parser = subparsers.add_parser(
            'sign', help='Use a jwks key to generate a signature for a file. (Assumes a json or yaml file)'
        )

        sign_operation_parser.add_argument(
            '--file',
            help='The path to the file you would like to sign. (Assumes a json or yaml file)'
        )

        sign_operation_parser.set_defaults(func='sign_operation')

        verify_operation_parser = subparsers.add_parser(
            'verify', help='Verify a signture with a known file. (Assumes a json file)'
        )

        verify_operation_parser.add_argument(
            '--file',
            help='The path to the file you would like to sign.'
        )

        verify_operation_parser.set_defaults(func='verify_operation')
        return parser.parse_args(args)

    def run(self):
        logger = logging.getLogger(__name__)
        self.config = self.parse_args(sys.argv[1:])
        if self.config.func == 'sign_operation':
            logger.info('Attempting to sign file: {}'.format(self.config.file))
            file_content = common.load_file(self.config.file)
            signing_object = operation.Sign()
            signing_object.load(file_content)
            jws = signing_object.jws()
            common.write_file(jws, '{}.jws'.format(self.config.file))
            logger.info('File signed.  Your signed file is now: {}.jws'.format(self.config.file))
            logger.info('To verify this file use cis_crypto verify --file {}.jws'.format(self.config.file))
        elif self.config.func == 'verify_operation':
            logger.info('Attempting verification of signature for file: {}'.format(self.config.file))
            everett_config = get_config()
            logger.info(
                'Attempting fetch of .well-known data from: {}'.format(
                    everett_config('public_key_name', namespace='cis', default='access-file-key.pub.pem')
                )
            )
            file_content = common.load_file(self.config.file)
            verify_object = operation.Verify()
            verify_object.load(file_content)
            try:
                jws = verify_object.jws()  # This will raise if the signature is invalid.
                logger.info('Signature verified for file: {}'.format(self.config.file))
            except jose.exceptions.JWSError:
                logger.error('The signature could not be verified.')
                sys.exit()
            sys.exit()
