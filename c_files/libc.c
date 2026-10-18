// Freestanding memory and string helpers the compiler may call implicitly.
typedef unsigned long size_t;
void* memcpy(void*d,const void*s,size_t n){ unsigned char*a=d; const unsigned char*b=s; while(n--) *a++=*b++; return d; }
void* memset(void*d,int c,size_t n){ unsigned char*a=d; while(n--) *a++=(unsigned char)c; return d; }
int memcmp(const void*x,const void*y,size_t n){ const unsigned char*a=x,*b=y; while(n--){ if(*a!=*b) return *a-*b; a++;b++; } return 0; }
size_t strlen(const char*s){ size_t n=0; while(s[n]) n++; return n; }
