# Protocol Buffers - Google's data interchange format
# Copyright 2008 Google Inc.  All rights reserved.
# https://developers.google.com/protocol-buffers/
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are
# met:
#
#     * Redistributions of source code must retain the above copyright
# notice, this list of conditions and the following disclaimer.
#     * Redistributions in binary form must reproduce the above
# copyright notice, this list of conditions and the following disclaimer
# in the documentation and/or other materials provided with the
# distribution.
#     * Neither the name of Google Inc. nor the names of its
# contributors may be used to endorse or promote products derived from
# this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
# A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
# OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
# SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
# LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
# DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
# THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

"""Implements the generate_py_protobufs command."""

__author__ = 'dlj@google.com (David L. Jones)'

from . import protoc_command_base

class generate_py_protobufs(protoc_command_base.ProtocCommandBase):
    """Generates Python sources for .proto files."""

    description = 'Generate Python sources for .proto files'
    user_options = [
        ('extra-proto-paths=', None,
         'Additional paths to resolve imports in .proto files.'),

        ('protoc=', None,
         'Path to a specific `protoc` command to use.'),
    ]
    boolean_options = ['recurse']

    def initialize_options(self):
        """Sets the defaults for the command options."""
        super().initialize_options()
        self.proto_paths = []
        self.extra_proto_paths = []
        self.output_dir = '.'

    def finalize_options(self):
        """Sets the final values for the command options.

        Defaults were set in `initialize_options`, but could have been changed
        by command-line options or by other commands.
        """
        super().finalize_options()

        self.ensure_string_list('extra_proto_paths')
        for extra_proto_path in self.extra_proto_paths:
            self.proto_paths.append(extra_proto_path)

        self.ensure_dirname('output_dir')

    def run(self):
        self.run_protoc(args=['--python_out=' + self.output_dir])
