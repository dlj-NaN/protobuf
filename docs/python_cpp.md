# Application note: Python/C++ protobufs

This application note describes how to make generated C++ message
implementations available to the Python runtime. In this configuration, some
Protobuf-intensive workloads may see substantial performance improvements.

This app note describes how to change between API implementations for the Python
Protobuf runtime, as of version 3.14. The techniques described in this document
rely on implementation details of the Python API, as well as build configuration
details for generating Python APIs that must have the matching C++ generated
code available. These techniques may not be suitable for all users, and may not
be applicable to future versions of the Protobuf suite.

## Background

The Protobuf Python runtime has multiple operating modes. In order of
performance, starting from the slowest:

-   All logic may be implemented in pure Python.
-   Messages may be backed by the "reflective" C++ API, i.e., the Python
    interfaces use the C++ runtime to defined message types and create and
    manipulate instances instances on-the-fly.
-   Messages may be backed by generated C++ code for corresponding messages.

The pure-Python mode is provided for completeness, and is needed for cases where
prebuilt Python extension DSOs are not suitable. The "reflective C++" mode
provides a substantial speedup over pure-Python -- typically 5-20x faster --
without requiring generated C++ code for user-provided `.proto` files (this is
currently the default mode, for example, when installing from PyPI). The third
mode (using generated C++ code) provides a further speedup of 4-5x above the C++
reflective implementation, but requires full transitive availability of
generated C++ for any message used from Python.

### Protobuf Python runtime behavior with (or without) C++

In the typical case, generated Python code is agnostic of the backing
implementation of the Protobuf Python API. In other words, when `a.proto` is
passed to the protocol compiler to generate `a_pb2.py`, the resulting file can
use any of the backing strategies described earlier. This is possible because
the generated file contains only enough definitions for a metaclass to construct
the Python types (at runtime, during import).

If the native extension module for the Python runtime is available, it provides
the metaclass implementations used to create all other types. Otherwise, the
pure-Python implementation metaclass implementations are used. This decision is
made once, during the (transitive) module execution phase of `google.protobuf`.

<aside>NOTE: In CPython, the imported Python module is cached by the
implementation of import, which is sufficient for maintaining necessary
coordination between certain Python objects (which are managed by the Python GC)
and their corresponding C++ implementations (which may have static lifetime
duration). This is considered an internal implementation detail, and so it is
strongly recommended _not_ to attempt to interact with import execution or
caching of any part of the Protobuf Python runtime, or of any Protobuf-generated
sources.</aside>

One key datum provided by the generated Python interfaces is the message
descriptor, which is embedded in generated Python files in serialized form. The
surrounding generated code provides the information used by the metaclass
implementations, but the descriptor is the key piece which is needed by the
Python Protobuf runtime itself (it is used, for example, to resolve extensions
during parsing). The generated Python code is structured to ensure that the
metaclass construction (which occurs during module evaluation, at import time)
is correctly sequenced with the availability of the descriptor (the Protobuf
runtime requires descriptors to be registered before certain operations, and the
metaclass enforces that the descriptor is available to the runtime before
classes which use the runtime can be created).

In the "reflective C++" mode, the descriptor is added to a Python-specific C++
`DescriptorDatabase`, which is subsequently used by a corresponding
`DescriptorPool` and `MessageFactory`. This Python-specific state uses the
Protobuf C++ reflection APIs internally, and exposes an API which can be
accessed from Python code.

In the "generated C++" mode, generated C++ types (including descriptors) are
registered with the Protobuf C++ runtime during global construction, as is
required by the Protobuf C++ runtime. This registration may happen during
dynamic loading, including during Python native extension module import. Even
with generated C++ message implementations, the same Python Protobuf API
implementation is used as in the "reflective C++" mode; however, the runtime
always prefers message implementations registered with the C++ runtime, so any
Protobuf types available through the C++ API are not added to the
Python-specific reflective implementation described previously. (This
effectively means that descriptor in the corresponding `_pb2.py` file is
ignored.) Furthermore, the C++ runtime requires that all dependencies are
linked, transitively (possibly dynamically). So, for example, if `a.proto`
imports and uses types from `b.proto`, then the generated C++ implementation for
`a.pb.cc` will require symbols from `b.pb.cc` (as required by the Protobuf C++
runtime); both `a_pb2.py` and `b_pb2.py` will provide structures used by the
chosen Python Protobuf metaclass implementations; and the descriptors from
`a.pb.cc` and `b.pb.cc` are registered with the Protobuf C++ runtime and shared
with the Protobuf Python runtime.

### Protobuf C++ dependency resolution

Python relies upon dynamic linking and loading for native extension modules. The
semantics of dynamic linking and loading vary across platforms, and a full
discussion is beyond the scope of this application note. However, some
requirements must be fulfilled by linking -- dynamic or not -- and are in-scope
for this application note.

The major requirement is that all Protobuf C++ code is linked, loaded, and
initialized _soundly_, across its dependencies, transitively. In addition to the
typical linking requirements, this also means that global constructors must
finish for all Protobuf types prior to certain operations using these types.

It is possible for C++ types to be provided by Python native extension modules;
however, care must be taken when loading these modules to ensure that any
symbols which may be needed by other native extension modules are made
available.

## Build strategies

<aside>NOTE: Examples below are based on a Linux build, and so presume POSIX and
ELF semantics. Similar functionality is available on other modern platforms, but
is outside the scope of this application note. Python extension modules built
through `distutils`/`setuptools` generally also imply use of default system
libraries, such as `libstdc++` and `libgcc_s`, although this varies across Linux
distributions, and may need to be matched to objects built from generated C++
code in some examples below.</aside>

### Pure Python runtime

When installing the `google.protobuf` Python package from sources, the default
installation will utilize the pure Python runtime implementation. This may be
unsuitably slow for applications which use Protobuf messages intensively.

Typical example of installing Pure Python from source:

```
~path/to/protobuf$ cd python
~path/to/protobuf/python$ python -m pip install .
```

<aside>Because the `google` prefix of `google.protobuf` is shared with other
projects, we strongly recommend using `pip` to install the Protobuf Python
runtime, and not `setup.py install`.</aside>

### C++-backed Python runtime

To build the Protobuf Python runtime so that it is backed by C++ API
implementation, the C++ runtime must first be built so it is available during
the build of, and at runtime for, the Protobuf Python runtime.

<aside>NOTE: The Python native extension module is version-locked to the C++
runtime. Attempting to use different versions will result in unpredictable
behavior at runtime.</aside>

#### Strategy 1: System-installed C++ runtime

In this strategy, the Protobuf C++ runtime is built and installed prior to
building the Protobuf Python runtime. This is the simplest option when a
"system" install is acceptable, for example, inside of a container image.

Example of building and installing the Protobuf C++ and Python runtimes:

```
~path/to/protobuf$ ./autogen.sh && ./configure && make -j$(nproc) install
~path/to/protobuf$ cd python
~path/to/protobuf/python$ python setup.py --cpp_implementation build
~path/to/protobuf/python$ python setup.py bdist_wheel
~path/to/protobuf/python$ python -m pip install dist/*.whl
```

<aside>NOTE: This strategy requires using `setup.py` to build the native
extension module, although we it is still strongly recommend using `pip` to
perform the package installation.</aside>

<aside>NOTE: Both the C++ runtime and Python native extension module are
version-locked. If the C++ runtime is already installed, then the Protobuf
Python native extension module runtime must be built using the same sources as
the C++ runtime.</aside>

#### Strategy 2: Extension-linked C++ runtime

In this strategy, the source-built C++ runtime is linked into the Protobuf
Python runtime's native extension module. This avoids the need to install
`libprotobuf.so` in a location searched during dynamic loading.

Example of building the Protobuf Python runtime with the C++ runtime linked in:

```
~path/to/protobuf$ ./autogen.sh && ./configure && make -j$(nproc)
~path/to/protobuf$ cd python
~path/to/protobuf/python$ python setup.py --cpp_implementation --compile_static_extension build
~path/to/protobuf/python$ python setup.py bdist_wheel
~path/to/protobuf/python$ python -m pip install dist/*.whl
```

<aside>NOTE: If any other modules form a dependency on symbols from the Protobuf
C++ runtime, transitively, then the Protobuf Python module must be imported in a
way that the symbols are available for subsequent dynamic loading and
linking. This can be achieved by setting `RTLD_GLOBAL` before importing
`google.protobuf`, and further ensuring that this import happens prior to any
other import which may require the symbols, transitively. As an additional
measure, it may be desirable to ensure that dependent DSOs (including Python
native extension modules) are built without a `DT_NEEDED` entry for
`libprotobuf.so`, to avoid loading multiple, conflicting versions of the
Protobuf C++ runtime.</aside>
