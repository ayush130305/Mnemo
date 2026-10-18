// Mini printf with %d %x %s, a ring-buffer logger, and message tables (text-heavy rodata).
#define UART (*(volatile unsigned*)0x10000000)
static void pc(char c){ UART=c; }
static void ps(const char*s){ while(*s) pc(*s++); }
static void pd(int v){ char b[12]; int n=0; if(v<0){pc('-');v=-v;} do{ b[n++]='0'+v%10; v/=10; }while(v); while(n) pc(b[--n]); }
static void px(unsigned v){ const char*h="0123456789ABCDEF"; for(int i=28;i>=0;i-=4) pc(h[(v>>i)&15]); }
static void pf(const char*f, unsigned a, unsigned b){
  unsigned args[2]={a,b}; int ai=0;
  while(*f){ if(*f!='%'){ pc(*f++); continue; } f++;
    switch(*f++){ case 'd': pd((int)args[ai++]); break; case 'x': px(args[ai++]); break; case 's': ps((const char*)args[ai++]); break; default: pc('%'); } }
}
static const char* const levels[] = {"DEBUG","INFO","NOTICE","WARNING","ERROR","CRITICAL"};
static const char* const msgs[] = {
 "boot sequence started, clock=%d kHz\r\n",
 "memory test passed, %d words checked at %x\r\n",
 "peripheral %s initialised\r\n",
 "temperature sensor reads %d millidegrees\r\n",
 "watchdog will expire in %d ticks\r\n",
 "unexpected interrupt number %d at pc=%x\r\n",
 "DMA transfer complete, %d bytes moved\r\n",
 "link is up, speed %d baud\r\n",
};
int main(void){
  for(int i=0;i<8;i++){ ps(levels[i%6]); ps(": "); pf(msgs[i], 1000*i+7, 0x1000*i); }
  pf("%s done\r\n",(unsigned)"selftest",0); for(;;);
}
