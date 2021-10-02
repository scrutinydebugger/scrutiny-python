#include <gtest/gtest.h>
#include "scrutiny.h"
#include "scrutiny_test.h"

class TestMemoryControl : public ScrutinyTest
{
protected:
   scrutiny::Timebase tb;
   scrutiny::MainHandler scrutiny_handler;

   TestMemoryControl() {}

   virtual void SetUp() 
   {
      scrutiny_handler.init();
      scrutiny_handler.enable_comm();
   }
};

TEST_F(TestMemoryControl, TestRead) 
{
  
}

