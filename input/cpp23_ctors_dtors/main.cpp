#include "common.hpp"
#include "section1.hpp"
#include "section2.hpp"
#include "section3.hpp"
#include "section4.hpp"
#include "section5.hpp"
#include "section6.hpp"
#include "section7.hpp"
#include "section8.hpp"
#include "section9.hpp"
#include "section10.hpp"
#include "section11.hpp"
#include "section12.hpp"

int main() {
    // All sections execute their objects. 
    // No logs are printed; step through with a debugger to observe lifetimes.
    section1::run();
    section2::run();
    section3::run();
    section4::run();
    section5::run();
    section6::run();
    section7::run();
    section8::run();
    section9::run();
    section10::run();
    section11::run();
    section12::run();
    
    return 0;
}
