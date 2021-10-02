#include <gtest/gtest.h>
#include "scrutiny.h"
#include "scrutiny_test.h"

class TestMemoryControl : public ::testing::Test 
{
protected:
   scrutiny::Timebase tb;
   scrutiny::MainHandler scrutiny_handler;

   TestMemoryControl() {}

   virtual void SetUp() 
   {
      scrutiny::Config config; 
      config.protocol_major = 1;
      config.protocol_minor = 0;

      scrutiny_handler.init(&config);
   }
};

TEST_F(TestMemoryControl, TestRead) 
{
  
}

