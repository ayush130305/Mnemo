// Small stack virtual machine with a bytecode program, opcode dispatch table and a hash map.
enum { OP_PUSH, OP_ADD, OP_SUB, OP_MUL, OP_DUP, OP_SWAP, OP_JNZ, OP_DEC, OP_STORE, OP_LOAD, OP_HALT, OP_AND, OP_OR, OP_XOR, OP_SHL, OP_SHR };
static const unsigned char prog[] = {
 OP_PUSH,10, OP_PUSH,1, OP_STORE,0, OP_PUSH,20, OP_STORE,1,
 OP_LOAD,0, OP_LOAD,1, OP_ADD, OP_STORE,0, OP_LOAD,1, OP_DEC, OP_DUP, OP_STORE,1, OP_JNZ,10,
 OP_LOAD,0, OP_PUSH,3, OP_SHL, OP_PUSH,255, OP_AND, OP_STORE,2, OP_HALT };
static int stack[32], sp, mem[8];
static int run(const unsigned char*p){
  unsigned pc=0; sp=0;
  for(;;){
    switch(p[pc++]){
      case OP_PUSH: stack[sp++]=p[pc++]; break;
      case OP_ADD: sp--; stack[sp-1]+=stack[sp]; break;
      case OP_SUB: sp--; stack[sp-1]-=stack[sp]; break;
      case OP_MUL: sp--; stack[sp-1]*=stack[sp]; break;
      case OP_AND: sp--; stack[sp-1]&=stack[sp]; break;
      case OP_OR:  sp--; stack[sp-1]|=stack[sp]; break;
      case OP_XOR: sp--; stack[sp-1]^=stack[sp]; break;
      case OP_SHL: sp--; stack[sp-1]<<=stack[sp]; break;
      case OP_SHR: sp--; stack[sp-1]>>=stack[sp]; break;
      case OP_DUP: stack[sp]=stack[sp-1]; sp++; break;
      case OP_SWAP:{ int t=stack[sp-1]; stack[sp-1]=stack[sp-2]; stack[sp-2]=t; break; }
      case OP_DEC: stack[sp-1]--; break;
      case OP_JNZ:{ int t=stack[--sp]; unsigned a=p[pc++]; if(t) pc=a; break; }
      case OP_STORE: mem[p[pc++]]=stack[--sp]; break;
      case OP_LOAD: stack[sp++]=mem[p[pc++]]; break;
      default: return mem[2];
    }
  }
}
struct ent { unsigned key; int val; struct ent*next; };
static struct ent pool[64], *tab[16]; static int used;
static void put(unsigned k,int v){ struct ent*e=&pool[used++]; e->key=k; e->val=v; e->next=tab[k&15]; tab[k&15]=e; }
static int get(unsigned k){ for(struct ent*e=tab[k&15];e;e=e->next) if(e->key==k) return e->val; return -1; }
int main(void){ int r=run(prog); for(unsigned i=0;i<40;i++) put(i*2654435761u, r+i); volatile int g=get(5*2654435761u); (void)g; for(;;); }
