# Research: Nuitka and free-threaded CPython

## Official guidance

The current Nuitka package metadata lists regular CPython 3.14 support, while the installed
Nuitka 4.1.3 command reports Python 3.14 as experimentally supported. The official manual
recommends `python -m nuitka`, Visual Studio 2022 or higher on Windows, and `--mode=standalone`
before `--mode=onefile`. MinGW64 is not a valid choice for Python 3.13 or later. Nuitka's current
roadmap explicitly says the no-GIL Python 3.13 variant is not working.

The package-configuration documentation describes YAML hooks for dynamic imports, data files,
DLLs, and anti-bloat changes. No custom configuration was required for this application: the
validated onefile smoke test and real output comparison found no missing package data or imports.

The performance guidance is a benchmark orientation, not a promise for this workload. The
application comparison therefore uses the repository's process-tree sampler, the same warm
source-bound ELF/index, and repeated runs. Onefile extraction/I/O is intentionally included in
the user-facing executable measurement and called out separately.

## Local compatibility observations

| Component | Result |
| --- | --- |
| CPython 3.14.6 + Nuitka 4.1.3 | onefile build and CLI smoke pass after two deferred-annotation fixes |
| CPython 3.14.6 free-threaded runtime | core project and psutil run; generated outputs match regular CPython |
| Scalene 2.3.0 on `cp314t` Windows | blocked while linking `python314.lib`; regular CPython remains supported |
| pyperf 2.10.0 and py-spy 0.4.2 | install/run as external or pure-Python tooling in the free-threaded environment |
| pyinstrument 5.1.3 | imports, but its `stat_profile` extension enables the GIL because it does not declare free-threaded safety |
| Nuitka 4.1.3 on `cp314t` | blocked in C compilation by free-threaded CPython internal API changes |

## References

- [Nuitka package configuration](https://nuitka.net/user-documentation/nuitka-package-config.html)
- [Nuitka performance](https://nuitka.net/user-documentation/performance.html)
- [Nuitka tips](https://nuitka.net/user-documentation/tips.html)
- [Nuitka setup and build](https://nuitka.net/user-documentation/tutorial-setup-and-build.html)
- [Nuitka user manual](https://nuitka.net/user-documentation/user-manual.html)
- [Nuitka roadmap](https://nuitka.net/changelog/roadmap.html)
- [Nuitka 4.1 release](https://nuitka.net/posts/nuitka-release-41.html)
