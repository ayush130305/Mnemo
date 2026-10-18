// Integer matrix multiply, FIR filter with fixed-point coefficients, ring buffers.
#define N 16
static int A[N][N], B[N][N], C[N][N];
static short coef[32] = {1,-2,4,-8,16,-32,64,-128,256,-512,1024,-2048,4096,-2048,1024,-512,512,-1024,2048,-4096,2048,-1024,512,-256,128,-64,32,-16,8,-4,2,-1};
static short ring[64];
static void mm(void){ for(int i=0;i<N;i++) for(int j=0;j<N;j++){ int s=0; for(int k=0;k<N;k++) s+=A[i][k]*B[k][j]; C[i][j]=s; } }
static int fir(int head){ int acc=0; for(int t=0;t<32;t++) acc += coef[t]*ring[(head-t)&63]; return acc>>10; }
int main(void){
  for(int i=0;i<N;i++) for(int j=0;j<N;j++){ A[i][j]=i+j; B[i][j]=i-j; }
  mm();
  int out=0; for(int n=0;n<64;n++){ ring[n&63]=(short)(C[n&15][(n>>2)&15]); out+=fir(n); }
  volatile int sink=out; for(;;);
}
