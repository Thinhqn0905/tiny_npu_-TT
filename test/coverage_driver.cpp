// TC-COVERAGE-BASE, REQ-NPU-001/003/004/006. Independent public-pin contract driver.
// Integer expected values come from mathematical signed/wrap/round/clamp rules.
// No DUT internals are read, forced, or used to calculate expected results.
#include "Vcoverage_top.h"
#include "verilated.h"
#include "verilated_cov.h"
#include <array>
#include <algorithm>
#include <cstdint>
#include <cstdlib>
#include <iostream>
#include <random>
#include <vector>

static uint64_t simulation_time=0;
double sc_time_stamp() { return double(simulation_time); }

struct Host {
    Vcoverage_top d;
    std::mt19937 rng{784736294};
    std::array<int32_t,4> acc{{0,0,0,0}};
    bool overflow=false;
    int mode=0,shift=0;
    uint64_t cycles=0,checks=0;
    [[noreturn]] void fail(const char* reason) {
        std::cerr<<"FAIL cycle="<<cycles<<" "<<reason<<std::endl; std::exit(1);
    }
    void check(bool value,const char* why) { ++checks; if(!value) fail(why); }
    int32_t wrap(int64_t v) { uint32_t u=uint32_t(v)&0xffffffu; return u&0x800000u ? int32_t(u)-16777216 : int32_t(u); }
    int32_t quant(int32_t a) {
        int64_t v=int64_t(a)+(shift ? (int64_t(1)<<(shift-1)) : 0);
        int64_t divisor=int64_t(1)<<shift;
        int64_t q=v>=0 ? v/divisor : -((-v+divisor-1)/divisor);
        return int32_t(std::max<int64_t>(mode==1 ? 0 : -128,std::min<int64_t>(127,q)));
    }
    void tick() {
        d.clk=0; d.eval(); ++simulation_time;
        d.clk=1; d.eval(); ++simulation_time;
        d.clk=0; d.eval(); ++cycles;
        check(d.uio_oe==0xe2,"OE");
        check((d.uio_out&0x1d)==0,"reserved output");
        check(((d.uio_out>>5)&1)==((d.uio_out>>6)&1),"completion flags");
    }
    void reset() {
        d.ui_in=0; d.uio_in=0; d.ena=1; d.rst_n=0; tick();
        check(d.uio_out==0,"reset status");
        d.rst_n=1; tick(); check(d.uio_out==2,"idle status");
        acc.fill(0); mode=shift=0; overflow=false;
    }
    void send(int value,bool cmd=false) {
        d.uio_in=0; d.eval(); int timeout=0;
        while(!(d.uio_out&2)) { tick(); if(++timeout>20) fail("ready timeout"); }
        d.ui_in=uint8_t(value); d.uio_in=(rng()&0xeau)|(cmd ? 5 : 1); tick();
        d.uio_in=0; d.eval();
    }
    void command(int value) { send(value,true); }
    void post(int s,int m) { shift=s; mode=m; command(0x40|(m<<4)|s); }
    void clear() { command(0x81); acc.fill(0); overflow=false; }
    void status() {
        d.uio_in=16; d.eval(); check(bool(d.uo_out&128)==overflow,"last-MAC overflow flag");
        d.uio_in=0; d.eval();
    }
    void outputs() {
        for(int pe=0;pe<4;++pe) {
            command(0x80|(pe<<4));
            check(d.uo_out==uint8_t(quant(acc[pe])),"quantized PE output");
        }
        status();
    }
    void tuple(std::array<int,4> x,bool last) {
        for(int v:x) send(v);
        check(!(d.uio_out&2),"ready during pending MAC");
        d.uio_in=0; tick();
        overflow=false;
        for(int r=0;r<2;++r) for(int c=0;c<2;++c) {
            int pe=r*2+c; int64_t exact=int64_t(acc[pe])+x[r]*x[c+2];
            overflow|=exact < -8388608 || exact > 8388607;
            acc[pe]=wrap(exact);
        }
        check(bool(d.uio_out&32)==last,"vector completion timing");
        if(last) check(!(d.uio_out&2),"ready during FINISH");
    }
    void vector(const std::vector<std::array<int,4>>& xs,int s,int m,bool do_clear=true) {
        command(int(xs.size())-1); post(s,m); if(do_clear) clear();
        for(size_t i=0;i<xs.size();++i) tuple(xs[i],i+1==xs.size());
        outputs();
    }
};

int main(int argc,char** argv) {
    Verilated::commandArgs(argc,argv);
    Host h; h.reset();
    // Exhaustive signed operand pairs; all four PE read selectors are checked.
    for(int a=-128;a<128;++a) for(int b=-128;b<128;++b)
        h.vector({{{a,(a==-128 ? 127 : -a),b,-b/2}}},0,0);
    // Deterministic full-range vector lengths, shifts and activation modes.
    for(int n=0;n<1024;++n) {
        int k=1+(h.rng()%64); std::vector<std::array<int,4>> xs;
        for(int i=0;i<k;++i) {
            std::array<int,4> x; for(int& v:x) v=int(h.rng()%256)-128; xs.push_back(x);
        }
        h.vector(xs,n%16,(n/16)%4);
    }
    // Positive and negative growth through multiple vectors without clearing.
    for(auto x:std::vector<std::array<int,4>>{{-128,-128,-128,-128},{-128,-128,127,127}}) {
        h.clear();
        for(int n=0;n<9;++n) h.vector(std::vector<std::array<int,4>>(64,x),0,0,false);
        h.vector({{{0,0,0,0}}},0,0,false); // overflow flag is not sticky
    }
    // Requantization boundaries from encodable biases and legal products.
    for(int m=0;m<4;++m) for(int s=0;s<16;++s)
        for(int a:std::vector<int>{-128,-127,-64,-3,-2,-1,0,1,2,3,63,64,126,127})
            h.vector({{{a,a,1,2}}},s,m);
    for(int code=0xc0;code<=0xff;++code) {
        auto prior=h.acc; h.command(code); h.tick();
        int bias=code-256; h.acc={{bias,bias,prior[0],prior[1]}}; h.overflow=false; h.outputs();
    }
    h.command(0x83); h.tick(); h.acc.fill(0); h.overflow=false; h.outputs();
    // Reset at idle and after each partial tuple position; asynchronous reset while disabled.
    for(int bytes=0;bytes<5;++bytes) {
        h.command(0); for(int i=0;i<bytes;++i) h.send(i+3);
        h.d.ena=0; h.d.rst_n=0; h.tick(); h.reset();
        h.vector({{{1,2,3,4}}},0,0);
    }
    // Disable/resume a pending tuple: exactly one MAC after re-enable.
    h.command(0); h.post(0,0); h.clear();
    for(int v:std::array<int,4>{{2,3,4,5}}) h.send(v);
    h.d.ena=0;
    for(int i=0;i<4;++i) { h.tick(); h.check(!(h.d.uio_out&2),"ready while disabled"); }
    h.d.ena=1; h.tick(); h.acc={{8,10,12,15}}; h.overflow=false; h.outputs();
    for(int i=0;i<4;++i) h.tick(); h.outputs();
    h.d.final();
    VerilatedCov::write("work/coverage/baseline/coverage.dat");
    std::cout<<"PASS TC-COVERAGE-BASE cycles="<<h.cycles<<" checks="<<h.checks<<" seed=784736294\n";
}
