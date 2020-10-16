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

"""Base Command class for running protoc."""

__author__ = 'dlj@google.com (David L. Jones)'

import glob
import os
import distutils.spawn as spawn
from distutils.cmd import Command
from distutils.errors import DistutilsOptionError, DistutilsExecError

class ProtocCommandBase(Command):
    """Runs the protoc protobuf compiler."""

    user_options = [
        ('extra-proto-paths=', None,
         'Additional paths to resolve imports in .proto files.'),

        ('include-dirs=', 'I',
         'Additional paths to resolve imports in .proto files.'),

        ('protoc=', None,
         'Path to a specific `protoc` command to use.'),
    ]
    boolean_options = ['recurse']

    def initialize_options(self):
        """Sets the defaults for the command options."""
        self.source_dir = None
        self.output_dir = '.'
        self.proto_root_path = None
        self.include_dirs = None
        self.proto_paths = []
        self.extra_proto_paths = []
        self.proto_files = None
        self.recurse = None
        self.protoc = None

    def finalize_options(self):
        """Sets the final values for the command options.

        Defaults were set in `initialize_options`, but could have been changed
        by command-line options or by other commands.
        """

        self.set_undefined_options(
            'build_ext',
            ('include_dirs', 'include_dirs'),
        )

        self.ensure_dirname('source_dir')
        self.ensure_dirname('output_dir')

        if self.include_dirs is not None:
            self.ensure_proto_path_list('include_dirs')
            self.proto_paths = self.include_dirs + self.proto_paths

        self.ensure_proto_path_list('proto_paths')
        self.ensure_proto_path_list('extra_proto_paths')

        if self.proto_root_path is None:
            self.proto_root_path = self.compute_proto_root_path()
            if self.proto_root_path != self.source_dir:
                self.announce(
                    'using computed proto_root_path: ' + self.proto_root_path,
                    level=2)

        self.ensure_dirname('proto_root_path')

        if not self.source_dir.startswith(self.proto_root_path):
            raise DistutilsOptionError(
                'source_dir ' + self.source_dir +
                ' is not under proto_root_path ' + self.proto_root_path)

        if self.recurse is None:
            self.recurse = True

        if self.proto_files is None:
            self.proto_files = self.find_proto_files()
            if not self.proto_files:
                self.warn('no .proto files were found under ' + self.source_dir)

        if self.protoc is None:
            self.protoc = os.getenv('PROTOC')

    def ensure_proto_path_list(self, option):
        """Ensure that 'option' is a valid list of values for --proto_path."""
        self.ensure_string_list(option)

        value = getattr(self, option)
        if value is None:
            return

        invalid_paths = []
        for proto_path in value:
            virtpath, sep, realpath = proto_path.partition('=')
            if not sep:
                if not os.path.isdir(proto_path):
                    invalid_paths.append(proto_path)
            else:
                if not os.path.exists(realpath):
                    invalid_paths.append(proto_path)

        if invalid_paths:
            raise DistutilsOptionError('invalid %s entry' % option,
                                       invalid_paths)

    def compute_proto_root_path(self):
        """Returns a value for proto_root_path.

        The returned value is based on self.source_path and self.proto_paths.
        This function is used by self.finalize_options, but it can be called
        separately, too.

        Returns:
          (str) An inferred value for proto_root_path.
        """

        # SUBTLE: if 'source_dir' is a subdirectory of any entry in
        # 'proto_paths', then in general, the shortest --proto_path prefix
        # (and the longest relative .proto filenames) must be used for
        # correctness. For example, consider:
        #
        #     source_dir = 'a/b/c'
        #     proto_paths = ['a/b', 'x/y']
        #
        # In this case, we must ensure that a/b/c/d/foo.proto resolves
        # canonically as c/d/foo.proto, not just d/foo.proto. Otherwise, this
        # import:
        #
        #     import "c/d/foo.proto";
        #
        # would result in different FileDescriptor.name keys from "d/foo.proto".
        # That will cause all the definitions in the file to be flagged as
        # duplicates, with an error similar to:
        #
        #     c/d/foo.proto: "packagename.MessageName" is already defined in file "d/foo.proto"
        #
        # For paths in self.proto_files, we transform them to be relative to
        # self.proto_root_path, which may be different from self.source_dir.
        #
        # Although the order of --proto_paths is significant, shadowed filenames
        # are errors: if 'a/b/c.proto' resolves to different files under two
        # different --proto_path arguments, then the path is rejected as an
        # error. (Implementation note: this is enforced in protoc's
        # DiskSourceTree class.)

        proto_root_path = os.path.normpath(self.source_dir)
        for root_candidate in (self.proto_paths + self.extra_proto_paths):
            root_candidate = os.path.normpath(root_candidate)
            if proto_root_path.startswith(root_candidate):
                # This candidate is shorter, so it is preferred.
                proto_root_path = root_candidate

        return proto_root_path

    def find_proto_files(self):
        """Globs and returns .proto files under source_dir."""

        files = glob.glob(os.path.join(self.source_dir, '*.proto'))
        if self.recurse:
            ext_glob = os.path.join(self.source_dir, '**', '*.proto')
            files.extend(glob.glob(ext_glob))

        # Make all the paths relative to self.proto_root.
        return [
            f.partition(self.proto_root_path + os.path.sep)[-1]
            for f in files
        ]

    def run_protoc(self, args):
        """Run the protoc compiler in a subprocess.

        Args:
          args: flags to control code generation (e.g., '--LANG_out=...').
        """

        # All proto file paths were adjusted in finalize_options to be relative
        # to self.proto_root_path.
        proto_paths = [
            '--proto_path=' + x
            for x in [self.proto_root_path] + (self.proto_paths or [])
        ]

        # Run protoc. We resolve via PATH if another value was not provided.
        if self.protoc is None:
            self.protoc = spawn.find_executable('protoc')
        spawn.spawn(
            [self.protoc] + proto_paths + args + self.proto_files,
            search_path=0)
