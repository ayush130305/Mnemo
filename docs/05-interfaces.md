# 5. Interfaces

[Back to the README](../README.md)

Three interfaces: AXI4 toward the processor, a simple synchronous port toward the memory, and an AXI4-Lite port for control.

**Processor side (data window).** AXI4 slave, 32-bit data, INCR bursts up to 16 beats (one line). Virtual address range 0 to V_BYTES-1. Reads and writes may stall with ready low while a page is expanded or a chunk is allocated. A write that cannot be satisfied because the pool is exhausted returns SLVERR; reads never fail except on an integrity error (also SLVERR, flagged in a register).

**Control side.** AXI4-Lite slave, separate base address, 32-bit registers (section 11). One interrupt line, level, cleared by writing the status register.

**Memory side (native port).** Word-addressed, synchronous, one outstanding request in v0:

| Signal   | Direction | Meaning                                               |
|----------|-----------|-------------------------------------------------------|
| m_req    | out       | A request is valid                                    |
| m_we     | out       | 1 = write, 0 = read                                   |
| m_addr   | out       | Physical word address (chunk number and word offset)  |
| m_wdata  | out       | Write data, 32 bits                                   |
| m_wstrb  | out       | Byte enables                                          |
| m_ready  | in        | Request accepted this clock                           |
| m_rvalid | in        | Read data valid (fixed latency in v0, variable later) |
| m_rdata  | in        | Read data, 32 bits                                    |

The native port is wrapped later: a block-RAM model first, then a QSPI PSRAM controller or a DDR port. Only the wrapper changes.
