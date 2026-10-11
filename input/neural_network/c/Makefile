CC      ?= cc
CFLAGS  ?= -O2 -std=c99 -Wall -Wextra
LDLIBS  ?= -lm

nn: neural_network.c
    $(CC) $(CFLAGS) neural_network.c -o nn $(LDLIBS)

run: nn
    ./nn

clean:
    rm -f nn

.PHONY: run clean
