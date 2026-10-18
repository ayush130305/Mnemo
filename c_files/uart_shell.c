// Tiny UART command shell: string parsing, hex printing, lookup tables.
#define UART (*(volatile unsigned*)0x10000000)
static void putc_(char c){ UART = c; }
static void puts_(const char*s){ while(*s) putc_(*s++); }
static void puthex(unsigned v){ const char*h="0123456789abcdef"; for(int i=28;i>=0;i-=4) putc_(h[(v>>i)&15]); }
static int strcmp_(const char*a,const char*b){ while(*a&&*a==*b){a++;b++;} return *a-*b; }
struct cmd { const char*name; const char*help; unsigned (*fn)(unsigned); };
static unsigned c_peek(unsigned a){ return *(volatile unsigned*)a; }
static unsigned c_poke(unsigned a){ *(volatile unsigned*)a = 0xdeadbeef; return a; }
static unsigned c_echo(unsigned a){ return a; }
static unsigned c_rev(unsigned a){ unsigned r=0; for(int i=0;i<32;i++){ r=(r<<1)|(a&1); a>>=1;} return r; }
static const struct cmd cmds[] = {
 {"peek","read a 32 bit word from memory",c_peek},
 {"poke","write 0xdeadbeef to memory",c_poke},
 {"echo","print the argument back",c_echo},
 {"rev","reverse the bits of the argument",c_rev},
};
static const char banner[] = "PicoRV32 shell v0.3 - type a command, arguments are hexadecimal\r\n";
static unsigned parse(const char*s){ unsigned v=0; while(*s){ char c=*s++; v<<=4; v|= (c>='a')? c-'a'+10 : c-'0'; } return v; }
int main(void){
  puts_(banner);
  const char* script[] = {"peek 100","poke 200","echo 1234","rev 1","rev ffff0000"};
  for(unsigned i=0;i<sizeof script/sizeof script[0];i++){
    char name[8]; const char*p=script[i]; int n=0; while(*p&&*p!=' '&&n<7) name[n++]=*p++; name[n]=0; if(*p==' ')p++;
    for(unsigned k=0;k<sizeof cmds/sizeof cmds[0];k++) if(!strcmp_(name,cmds[k].name)){ puts_(cmds[k].help); puts_(" -> "); puthex(cmds[k].fn(parse(p))); puts_("\r\n"); }
  }
  for(;;);
}
