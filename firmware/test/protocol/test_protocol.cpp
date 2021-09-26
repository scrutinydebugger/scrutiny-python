#include <gtest/gtest.h>

// Demonstrate some basic assertions.
TEST(TestProtocol, DummyTest) {
  // Expect two strings not to be equal.
  EXPECT_STRNE("Protocol", "protocol");
  // Expect equality.
  EXPECT_EQ(7 * 6, 42);
}