// CRC32 table build, insertion sort and a checksum over a static array.
static unsigned table[256];
static unsigned data[512];
static void mk(void){ for(unsigned i=0;i<256;i++){ unsigned c=i; for(int k=0;k<8;k++) c = (c&1)? 0xedb88320u^(c>>1) : c>>1; table[i]=c; } }
static unsigned crc(const unsigned char*p,unsigned n){ unsigned c=~0u; while(n--) c = table[(c^*p++)&255]^(c>>8); return ~c; }
static void isort(unsigned*a,int n){ for(int i=1;i<n;i++){ unsigned v=a[i]; int j=i-1; while(j>=0&&a[j]>v){a[j+1]=a[j];j--;} a[j+1]=v; } }
int main(void){
  mk(); unsigned s=12345;
  for(int i=0;i<512;i++){ s = s*1103515245u+12345u; data[i]=s>>8; }
  isort(data,512);
  volatile unsigned r = crc((const unsigned char*)data,sizeof data);
  for(;;);
  return r;
}
