import logging

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


class StructuredLogger(object):
    def __init__(self, name, level):
        self.name = name
        self.level = level
        self.set_stream_logger()

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

    def get_logger(self):
        logging.getLogger(self.name).addHandler(logging.NullHandler())
