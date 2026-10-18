# 3. System context and block diagram

[Back to the README](../README.md)

<img src="media/image1.png" style="width:6in;height:3.53571in" alt="memory coprocessor · 8 blocks between processor and memory" />

memory coprocessor · 8 blocks between processor and memory

The processor sees an ordinary AXI4 memory. Inside, a request goes front end, translation, then the codec bank or page engine, with the allocator owning every physical chunk and the arbiter giving host accesses the memory port first. The learning block watches decisions and outcomes and steers codec, slot and hotness; it never sits on the data path itself. Section 4 describes each block, section 10 the flows.
