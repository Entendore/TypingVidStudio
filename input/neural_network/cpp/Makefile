CXX      ?= g++
CXXFLAGS ?= -O2 -std=c++17 -Wall

nn: neural_network.cpp
    $(CXX) $(CXXFLAGS) neural_network.cpp -o nn

run: nn
    ./nn

clean:
    rm -f nn

.PHONY: run clean
