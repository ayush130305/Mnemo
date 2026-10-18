# Mnemo

Mnemo is a coprocessor that sits between a processor and its memory. It stores data compressed and losslessly, manages the physical memory itself, and learns which codec and layout suit each region, so the processor sees an ordinary memory.

**Status:** Python simulator and full coprocessor model working (0 mismatches against a shadow memory). RTL not started.

**Results so far** (57-file corpus, 1.43 MB, stored size including 36 B metadata per page):

| Approach | Ratio |
| --- | ---: |
| Line codecs only (zero, BDI, FPC) | 1.52 |
| LZSS pages | 2.21 |
| xz pages | 2.53 |

Line codecs alone give about 1.0x on real code. The value of the learning block is latency and hot-page prediction, not size. Details: [showcase/FEATURES.md](showcase/FEATURES.md) and [showcase/results/](showcase/results/).

## Architecture spec

| Section |
| --- |
| [1. Goal and scope](docs/01-goal-and-scope.md) |
| [2. Parameters and assumptions](docs/02-parameters-and-assumptions.md) |
| [3. System context and block diagram](docs/03-system-context.md) |
| [4. Blocks and their responsibilities](docs/04-blocks-and-their-responsibilities.md) |
| [5. Interfaces](docs/05-interfaces.md) |
| [6. Address translation and page metadata](docs/06-translation-and-page-table.md) |
| [7. Compression engines and the codec selector](docs/07-compression-and-codec-selector.md) |
| [8. Allocator: chunk pool, exceptions, repack, pressure](docs/08-allocator-and-pressure.md) |
| [9. Learning and policy block](docs/09-learning-and-policy-block.md) |
| [10. Data flows](docs/10-data-flows.md) |
| [11. Register map](docs/11-register-map.md) |
| [12. Integrity, safety, security](docs/12-integrity-safety-security.md) |
| [13. Verification plan and metrics](docs/13-verification-plan-and-metrics.md) |
| [14. Build plan and boards](docs/14-build-plan-and-boards.md) |
| [15. Open questions and prior art](docs/15-open-questions-and-prior-art.md) |
| [16. Changes since v0.1 (simulator findings)](docs/16-changes-since-v0-1.md) |

The spec is also kept as a Word file: [showcase/Mnemo_Architecture_Spec_v0.1.docx](showcase/Mnemo_Architecture_Spec_v0.1.docx).

## Repository layout

| Folder | Content |
| --- | --- |
| [docs/](docs/) | The architecture spec, one file per section |
| [showcase/](showcase/) | What we did: spec (Word), results, feature list |
| [test_files/](test_files/) | Test corpus (firmware, native code, data, controls) |
| [c_files/](c_files/) | C sources and linker script for the firmware in the corpus |
| [python_files/](python_files/) | Codecs, corpus builder, comparator, policy and block-size studies |
| [simulator/](simulator/) | Page simulator, visual simulator, full coprocessor model and its tests |
| [rtl/](rtl/) | Verilog and the RTL simulation runner |

## Run

See [RUN.md](RUN.md).
