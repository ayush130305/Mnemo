# 11. Register map

[Back to the README](../README.md)

AXI4-Lite, 32-bit registers, offsets in bytes from the control base. R = read only, RW = read and write, W1C = write 1 to clear.

| Offset | Name         | Access | Meaning                                                                                                      |
|--------|--------------|--------|--------------------------------------------------------------------------------------------------------------|
| 0x00   | ID           | R      | Magic and version (0x4D435000 plus version)                                                                  |
| 0x04   | CTRL         | RW     | Bit 0 enable, bit 1 bypass (raw only), bit 2 debug check on write, bit 3 learning enable, bit 4 start repack |
| 0x08   | STATUS       | W1C    | Bit 0 low pressure, 1 critical, 2 full, 3 integrity error, 4 table error                                     |
| 0x0C   | IRQ_EN       | RW     | Interrupt enables, same bits as STATUS                                                                       |
| 0x10   | POOL_CHUNKS  | R      | Total chunks                                                                                                 |
| 0x14   | FREE_CHUNKS  | R      | Free chunks now                                                                                              |
| 0x18   | EFF_CAPACITY | R      | Estimated bytes still storable                                                                               |
| 0x1C   | RATIO        | R      | Current ratio, fixed point 8.8                                                                               |
| 0x20   | THRESH       | RW     | Low and critical thresholds in percent                                                                       |
| 0x24   | POLICY0      | RW     | Prediction margin, explore interval, cold threshold                                                          |
| 0x28   | POLICY1      | RW     | Region size, slot coverage percent                                                                           |
| 0x2C   | FORCE        | RW     | Force a codec for all writes (0 = learned)                                                                   |
| 0x30   | CNT_READ     | R      | Reads served                                                                                                 |
| 0x34   | CNT_WRITE    | R      | Writes served                                                                                                |
| 0x38   | CNT_EXC      | R      | Exceptions created                                                                                           |
| 0x3C   | CNT_REPACK   | R      | Pages repacked                                                                                               |
| 0x40   | CNT_LZ       | R      | LZ compressions and expansions                                                                               |
| 0x44   | CNT_PRED     | R      | Predictions made and correct (two halves)                                                                    |
| 0x48   | CNT_PTE_MISS | R      | Page table cache misses                                                                                      |
| 0x4C   | CNT_MISMATCH | R      | Debug check mismatches (must stay 0)                                                                         |
| 0x50   | TEL_HEAD     | R      | Telemetry write index                                                                                        |
| 0x54   | TEL_TAIL     | RW     | Telemetry read index                                                                                         |
| 0x58   | TEL_DATA     | R      | Next 32-bit word of the event at the tail                                                                    |
| 0x5C   | PT_ADDR      | RW     | Debug: page number to inspect                                                                                |
| 0x60   | PT_DATA      | R      | Debug: PTE word, auto-increments                                                                             |

The simulator exposes the same names so one test script drives both.
