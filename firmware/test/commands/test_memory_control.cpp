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
      scrutiny_handler.init();
   }
};

TEST_F(TestMemoryControl, TestRead) 
{
  
}

