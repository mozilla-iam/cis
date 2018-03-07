import datetime
import logging
import watchtower

"""
The MIT License (MIT)

Copyright (c) 2016 ThreatResponse https://github.com/threatresponse

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

"""


class CISLogger(object):
    def __init__(
        self, name, level, cis_logging_output=None, cis_cloudwatch_log_group=None
    ):
        self.cis_logging_output = cis_logging_output
        self.cis_cloudwatch_log_group = cis_cloudwatch_log_group
        self.name = name
        self.level = self.get_level(level)

    def get_level(self, level):
        if level == 'INFO':
            return logging.INFO
        if level == 'DEBUG':
            return logging.DEBUG
        if level == 'ERROR':
            return logging.ERROR
        if level == 'WARN':
            return logging.WARN

        return logging.INFO

    def logger(self):
        if self.cis_logging_output == 'cloudwatch':
            return CloudWatchLogger(self.name, self.level, self.cis_cloudwatch_log_group)
        else:
            return StructuredLogger(self.name, self.level)


class StructuredLogger(object):
    def __init__(self, name, level):
        self.name = name
        self.level = level
        self.set_stream_logger()
        self.logger = None

    def set_stream_logger(self, format_string=None):
        """Stream logger class borrowed from https://github.com/threatresponse/aws_ir."""

        if not format_string:
            format_string = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

        time_format = "%Y-%m-%dT%H:%M:%S"

        logger = logging.getLogger(self.name)
        logger.setLevel(self.level)
        streamHandler = logging.StreamHandler()
        streamHandler.setLevel(self.level)
        streamFormatter = logging.Formatter(format_string, time_format)
        streamHandler.setFormatter(streamFormatter)
        logger.addHandler(streamHandler)
        self.logger = logger

    def get_logger(self):
        if self.logger:
            return self.logger
        else:
            self.set_stream_logger()
            return self.logger


class CloudWatchLogger(object):
    def __init__(self, name, level, log_group_name):
        self.name = name
        self.level = level
        self.log_group_name = log_group_name
        self.set_stream_logger()
        self.logger = None

    def set_stream_logger(self):
        logger = logging.getLogger(self.name)
        logger.setLevel(self.level)
        now = datetime.datetime.now()
        stream_name = "{}/{}/{}".format(now.year, now.month, now.day)
        logger.addHandler(
            watchtower.CloudWatchLogHandler(
                log_group='/cis/{}'.format(self.log_group_name),
                stream_name=stream_name
            )
        )
        self.logger = logger

    def get_logger(self):
        if self.logger:
            return self.logger
        else:
            self.set_stream_logger()
            return self.logger
