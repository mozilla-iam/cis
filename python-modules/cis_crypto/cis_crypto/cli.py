#!/usr/bin/env python3
import argparse
import logging
import sys


logger = logging.getLogger(__name__)


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

        top_level_args = parser.add_argument_group()

        top_level_args.add_argument(
            '--info',
            help='Show your mozilla-iam configuration information.'
        )

        subparsers = parser.add_subparsers(dest='cryptographic-operation')
        subparsers.required = True

        sign_operation_parser = subparsers.add_parser(
            'sign', help='Use a jwks key to generate a signature for a file.'
        )

        sign_operation_parser.add_argument(
            '--key-id',
            help='The key_id of the key you would like to try and retrieve to sign with.'
        )

        sign_operation_parser.add_argument(
            '--file',
            help='The path to the file you would like to sign. (Assumes a json or yaml file)'
        )

        verify_operation_parser = subparsers.add_parser(
            'verify', help='Verify a signture with a known file. (Assumes a json file)'
        )

        verify_operation_parser.add_argument(
            '--file',
            help='The path to the file you would like to sign.'
        )

        return parser.parse_args(args)

    def run(self):
        self.config = self.parse_args(sys.argv[1:])
