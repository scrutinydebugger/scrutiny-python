/*
This example is a dummy project that shows a fictive embedded application that does a power up sequence
of a fictive power supply using a Finite State Machine. The purpose of this example is to show how we can use Scrutiny 
to do Hardware In The Loop testing by controlling the flow of the application, reading/writing hardware IOs and reading 
internal states.

The file is presented as a single-file project that aggregates many files. Each file is not complete on purpose. They only show
the code relevant to this example.
*/

// time.hpp
#include <cstdint>
uint32_t timestamp_ms();        // Reads an absolute monotonic timestamp.
