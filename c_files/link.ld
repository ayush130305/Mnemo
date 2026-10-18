/* Single 32 KB RAM image at 0, like a PicoRV32 SoC with BRAM. */
MEMORY { RAM (rwx) : ORIGIN = 0x0, LENGTH = 32K }
SECTIONS {
  .text : { *(.init) *(.text*) *(.rodata*) *(.srodata*) } > RAM
  .data : { *(.data*) *(.sdata*) } > RAM
  .bss  : { _bss_start = .; *(.bss*) *(.sbss*) *(COMMON) _bss_end = .; } > RAM
  _stack_top = ORIGIN(RAM) + LENGTH(RAM);
}
